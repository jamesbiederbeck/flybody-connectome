"""Run the closed leg loop and log every tick.

Ground contact and joint deviation drive leg afferents; leg motor-neuron rates
drive the leg joints. See `fly.legs` for exactly which parts of that mapping
come from the reconstruction and which are placeholders -- the short version is
that motor side, leg and muscle identity are real, the muscle-to-joint
assignment is inferred from muscle names, and the afferent-to-leg assignment is
arbitrary because the data has no segment label for afferents.

The wings are left alone here. This is the leg loop on its own, so anything
that moves is attributable to it.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ticks", type=int, default=600)
    p.add_argument("--settle-ticks", type=int, default=60)
    p.add_argument("--dataset", default="malecns_v1")
    p.add_argument("--brain-hz", type=float, default=30.0)
    p.add_argument("--spawn-height-mm", type=float, default=2.0)
    p.add_argument("--proprioceptive-gain", type=float, default=6.0)
    p.add_argument("--tactile-gain", type=float, default=8.0)
    p.add_argument("--motor-gain", type=float, default=0.02)
    p.add_argument("--body", action="store_true",
                   help="Also drive halteres, abdomen and neck from their own "
                        "motor neurons (fly.motor). Off by default so leg-only "
                        "runs stay comparable to earlier ones.")
    p.add_argument("--frozen-sense", action="store_true",
                   help="Keep the motor path connected and freeze the sensory "
                        "currents at their first-tick values. This is the real "
                        "control: it asks whether the *sensing* is doing "
                        "anything, with total injected drive held comparable. "
                        "Same shape as fly.play's --frozen-vision.")
    p.add_argument("--no-sense", action="store_true",
                   help="Keep the motor path connected and inject no sensory "
                        "current at all. Stronger than --frozen-sense, but it "
                        "also moves the network's operating point, so a "
                        "difference here is not cleanly attributable to sensing.")
    p.add_argument("--open-loop", action="store_true",
                   help="Never write the actuators. This is a weak control -- it "
                        "only shows that actuator writes move the body, which is "
                        "not in question. Kept for completeness.")
    p.add_argument("--video", default=None,
                   help="Write an mp4 of the run through MuJoCo's offscreen renderer")
    p.add_argument("--playback-speed", type=float, default=0.04,
                   help="Seconds of simulation per 25fps frame; 0.04 gives a "
                        "watchable pace for a standing fly, not a wingbeat")
    p.add_argument("--camera-res", type=int, nargs=2, default=(480, 640))
    p.add_argument("--seed", type=int, default=20260919)
    p.add_argument("--out", default=str(ROOT / "outputs/walk/run.npz"))
    args = p.parse_args()

    from connectome_sim.native import NativeBrain
    from fly import body as body_mod
    from fly import legs as legs_mod
    from fly import motor as motor_mod
    from fly.play import _build_receptor_map

    graph = ROOT / "outputs/connectome_sim" / args.dataset / "graph.npz"
    brain = NativeBrain(str(graph))
    fly = body_mod.build(world="flat", spawn_height_mm=args.spawn_height_mm)
    mapping = _build_receptor_map(brain, fly, graph)

    physics_dt = float(fly.model.opt.timestep)
    duration_ms = 1000.0 / args.brain_hz
    substeps = max(1, int(round((duration_ms / 1000.0) / physics_dt)))
    for _ in range(args.settle_ticks * substeps):
        fly.step()

    loop = legs_mod.LegLoop(brain, fly, proprioceptive_gain=args.proprioceptive_gain,
                            tactile_gain=args.tactile_gain, motor_gain=args.motor_gain,
                            seed=args.seed)
    body = motor_mod.BodyMap(brain, fly, gain=args.motor_gain) if args.body else None
    joint_keys = sorted(loop.actuators)
    start_xyz = np.asarray(fly.data.xpos[1], float).copy()

    # The halteres are the point of the body map: the repo's own README records
    # them moving 3e-06 rad because nothing ever commanded them. Track the
    # actual joint excursion so that number can be replaced with a measurement.
    import mujoco as _mj
    haltere_qpos = []
    for _side in ("l", "r"):
        _jid = _mj.mj_name2id(fly.model, _mj.mjtObj.mjOBJ_JOINT,
                              f"{fly.name}/c_thorax-{_side}_haltere-pitch")
        if _jid >= 0:
            haltere_qpos.append(int(fly.model.jnt_qposadr[_jid]))
    haltere = np.zeros((args.ticks, len(haltere_qpos)), np.float64)

    renderer = None
    if args.video:
        from flygym.rendering import Renderer
        from fly.body import SCENE_CAMERA
        Path(args.video).parent.mkdir(parents=True, exist_ok=True)
        renderer = Renderer(fly.model, [SCENE_CAMERA],
                            camera_res=tuple(args.camera_res),
                            playback_speed=args.playback_speed)

    currents = np.zeros((args.ticks, len(legs_mod.LEGS), 2), np.float32)
    commands = np.zeros((args.ticks, len(joint_keys)), np.float32)
    motor_spikes = np.zeros((args.ticks, len(joint_keys)), np.int64)
    network = np.zeros(args.ticks, np.int64)
    pose = np.zeros((args.ticks, 13), np.float64)
    contacts = np.zeros(args.ticks, np.int64)
    started = time.time()
    frozen_stim = None

    for tick in range(args.ticks):
        stim = loop.sense(fly)
        if args.no_sense:
            stim = None
        elif args.frozen_sense:
            if frozen_stim is None:
                frozen_stim = stim
            stim = frozen_stim
        if stim:
            by_cells = {int(i[0]) if len(i) else -1: c for i, c in stim}
            for li, leg in enumerate(legs_mod.LEGS):
                for ci, key in enumerate(("proprioceptive", "tactile")):
                    idx = loop.sensory[leg].get(key)
                    if idx is not None and len(idx):
                        currents[tick, li, ci] = by_cells.get(int(idx[0]), 0.0)

        light = mapping(fly.ommatidia())
        counts, _ = brain.step(light, duration_ms, stimulation=stim)
        counts = np.asarray(counts)
        network[tick] = int(counts.sum())

        for j, key in enumerate(joint_keys):
            leg, segment, axis = key
            groups = loop.motor[leg][(segment, axis)]
            motor_spikes[tick, j] = int(sum(int(counts[idx].sum()) for idx, _ in groups))

        if not args.open_loop:
            cmd = loop.act(counts, fly, duration_ms / 1000.0)
            for j, key in enumerate(joint_keys):
                commands[tick, j] = cmd.get(key, 0.0)
            if body is not None:
                body.act(counts, fly, duration_ms / 1000.0)

        for _ in range(substeps):
            fly.step()
            if renderer is not None:
                renderer.render_as_needed(fly.data)

        d = fly.data
        pose[tick] = np.concatenate([np.asarray(d.xpos[1], float),
                                     np.asarray(d.xquat[1], float),
                                     np.asarray(d.cvel[1][3:], float),
                                     np.asarray(d.cvel[1][:3], float)])
        contacts[tick] = int(d.ncon)
        for h, adr in enumerate(haltere_qpos):
            haltere[tick, h] = float(d.qpos[adr])

    if renderer is not None:
        renderer.save_video(Path(args.video))
        renderer.close()
    displacement = float(np.linalg.norm(np.asarray(fly.data.xpos[1], float) - start_xyz))
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    meta = {
        "experiment": "walk",
        "condition": ("open_loop" if args.open_loop else
                      "no_sense" if args.no_sense else
                      "frozen_sense" if args.frozen_sense else "closed"),
        "open_loop": args.open_loop,
        "frozen_sense": args.frozen_sense,
        "no_sense": args.no_sense,
        "ticks": args.ticks,
        "brain_hz": args.brain_hz,
        "substeps_per_tick": substeps,
        "gains": {"proprioceptive": args.proprioceptive_gain,
                  "tactile": args.tactile_gain, "motor": args.motor_gain},
        "seed": args.seed,
        "joint_columns": ["/".join(k) for k in joint_keys],
        "leg_order": list(legs_mod.LEGS),
        "current_columns": ["proprioceptive", "tactile"],
        "mapping": loop.summary(),
        "mean_network_spikes": float(network.mean()),
        "motor_spikes_total": int(motor_spikes.sum()),
        "command_abs_mean": float(np.abs(commands).mean()),
        "command_abs_max": float(np.abs(commands).max()),
        "thorax_displacement_mm": round(displacement, 4),
        "contacts_mean": float(contacts.mean()),
        "body_map": body.report if body is not None else None,
        "haltere_excursion_rad": (float(haltere.max() - haltere.min())
                                  if haltere.size else None),
        "haltere_std_rad": float(haltere.std()) if haltere.size else None,
        "video": args.video,
        "wall_seconds": round(time.time() - started, 1),
    }
    np.savez_compressed(out, currents=currents, commands=commands,
                        motor_spikes=motor_spikes, network_spikes=network,
                        pose=pose, contacts=contacts, haltere=haltere,
                        joint_columns=np.array(["/".join(k) for k in joint_keys]),
                        leg_order=np.array(list(legs_mod.LEGS)))
    out.with_suffix(".json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps({k: v for k, v in meta.items() if k != "mapping"}, indent=2))


if __name__ == "__main__":
    main()
