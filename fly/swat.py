"""Experiment: a fly swatter descends on the fly, and we watch for a response.

The connectome contains the whole canonical escape pathway. Looming-sensitive
visual projection neurons -- LPLC2 (185 cells), LC4 (126), LC6 (124), LPLC1
(134) -- converge on the giant fibre DNp01 (2 cells), with the giant-fibre
connecting cells GFC1-GFC4 alongside. In a real fly an approaching object drives
LPLC2 and LC4, the giant fibre fires, and the animal takes off. Every part of
that circuit is present here and none of it has ever been given an approaching
object.

So: put a real swatter in the scene, drive it down at the fly, and record what
each stage does as a function of distance. Nothing is injected. The only input
is the picture reaching the eye cameras.

## Conditions

    live     swatter descends, retina sees it
    frozen   swatter descends, retinal input frozen at tick 0
    absent   no swatter, same duration

`frozen` is the control that matters, and it is the one this project learned to
run the hard way: it keeps the entire motor path connected and cuts only the
sensing, so a difference between `live` and `frozen` is attributable to the fly
seeing the swatter rather than to anything else in the loop. `absent` bounds
what the scene contributes at all.

If `live` and `frozen` are indistinguishable, the fly does not see it. That is a
real result about this model and should be reported as one.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

# Stages of the escape pathway, coarse to specific.
POPULATIONS = {
    "LPLC2": "type", "LC4": "type", "LC6": "type", "LPLC1": "type",
    "DNp01": "type", "GFC1": "type", "GFC2": "type",
}


def readouts(brain):
    from connectome_sim.physiology.common import annotations
    a = annotations(brain.ids)
    t = a.type.fillna("")
    groups = {name: np.flatnonzero((t == name).to_numpy()).astype(np.int32)
              for name in POPULATIONS}
    groups["photoreceptor"] = np.asarray(brain.retina, dtype=np.int32)
    groups["lamina"] = np.asarray(brain.lamina, dtype=np.int32)
    groups["visual_projection"] = np.flatnonzero(
        (a.superclass == "visual_projection").to_numpy()).astype(np.int32)
    groups["descending"] = np.flatnonzero(
        (a.superclass == "descending_neuron").to_numpy()).astype(np.int32)
    groups["vnc_motor"] = np.flatnonzero(
        (a.superclass == "vnc_motor").to_numpy()).astype(np.int32)
    groups["dlm"] = np.flatnonzero(t.str.startswith("DLMn").to_numpy()).astype(np.int32)
    return {k: v for k, v in groups.items() if len(v)}


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ticks", type=int, default=200)
    p.add_argument("--settle-ticks", type=int, default=60)
    p.add_argument("--condition", choices=("live", "frozen", "absent"), default="live")
    p.add_argument("--start-mm", type=float, default=60.0, help="swatter height at tick 0")
    p.add_argument("--stop-mm", type=float, default=3.0,
                   help="height at the final tick; the fly's back is near 1.5")
    p.add_argument("--brain-hz", type=float, default=30.0)
    p.add_argument("--dataset", default="malecns_v1")
    p.add_argument("--motor-gain", type=float, default=5.0)
    p.add_argument("--inject-lamina", type=float, default=None,
                   help="Bypass the photoreceptor transfer function entirely and "
                        "drive the lamina directly, with this as the peak current. "
                        "The photoreceptor curve compresses a 44%% luminance change "
                        "into under 3%% of current even after light adaptation; "
                        "injecting one layer deeper sets the gain by hand instead. "
                        "Each lamina cell is driven by the mean luminance of the "
                        "photoreceptors that actually synapse onto it, taken from "
                        "the graph, so the retinotopy is the reconstruction's.")
    p.add_argument("--lamina-reference", type=float, default=0.53,
                   help="Luminance treated as neutral; the measured scene median. "
                        "Deviations from it are what gets injected.")
    p.add_argument("--lamina-scale", type=float, default=0.3,
                   help="Luminance deviation mapped to the full injected current. "
                        "Fixed, not per-frame: normalising by each frame's own "
                        "range divides out the stimulus.")
    p.add_argument("--no-motor", action="store_true",
                   help="Run with no leg/body current injection at all. The "
                        "motor loop drives the network to ~59k spikes/tick "
                        "against a ~21k resting rate, which is the saturated "
                        "regime this project has characterised elsewhere; a "
                        "looming response has to be looked for outside it.")
    p.add_argument("--video", default=None)
    p.add_argument("--playback-speed", type=float, default=1.0,
                   help="Seconds of simulation per second of video. 1.0 is real "
                        "time. fly/render.py defaults to 0.005 because it exists "
                        "to inspect a 4.6 ms wingbeat; this run is a 6.7 s "
                        "descent, and at that default it becomes a 2:46 video of "
                        "a swatter moving imperceptibly.")
    p.add_argument("--out", default=None)
    args = p.parse_args()

    from connectome_sim.native import NativeBrain
    from fly import body as body_mod
    from fly import legs as legs_mod
    from fly import motor as motor_mod
    from fly.play import _build_receptor_map

    graph = ROOT / "outputs/connectome_sim" / args.dataset / "graph.npz"
    brain = NativeBrain(str(graph))
    fly = body_mod.build(world="flat", spawn_height_mm=2.0,
                         swatter=args.condition != "absent",
                         swatter_start_mm=(0.0, 0.0, args.start_mm))
    mapping = _build_receptor_map(brain, fly, graph)
    groups = readouts(brain)

    # Retina -> lamina map, straight off the CSR adjacency: for each lamina
    # cell, which photoreceptors reach it. 2,440 of 7,114 lamina cells receive
    # retinal input, a median of 4 receptors each.
    lamina_src = None
    if args.inject_lamina is not None:
        import collections
        retina = set(int(i) for i in np.asarray(brain.retina))
        pos = {int(i): k for k, i in enumerate(np.asarray(brain.retina))}
        inc = collections.defaultdict(list)
        for i in retina:
            for e in range(int(brain.ptr[i]), int(brain.ptr[i + 1])):
                j = int(brain.post[e])
                inc[j].append(pos[i])
        lam = [j for j in (int(x) for x in np.asarray(brain.lamina)) if j in inc]
        lamina_cells = np.array(lam, dtype=np.int32)
        # Flat index array plus offsets, so the per-tick reduction is vectorised.
        counts_per = np.array([len(inc[j]) for j in lam], dtype=np.int64)
        flat = np.concatenate([np.array(inc[j], dtype=np.int64) for j in lam])
        offsets = np.concatenate([[0], np.cumsum(counts_per)])
        lamina_src = (lamina_cells, flat, offsets, counts_per)

    physics_dt = float(fly.model.opt.timestep)
    duration_ms = 1000.0 / args.brain_hz
    substeps = max(1, int(round((duration_ms / 1000.0) / physics_dt)))
    for _ in range(args.settle_ticks * substeps):
        fly.step()

    loop = legs_mod.LegLoop(brain, fly, motor_gain=args.motor_gain)
    body = motor_mod.BodyMap(brain, fly, gain=args.motor_gain)
    start_xyz = np.asarray(fly.data.xpos[1], float).copy()

    renderer = None
    if args.video:
        from flygym.rendering import Renderer
        from fly.body import SCENE_CAMERA
        Path(args.video).parent.mkdir(parents=True, exist_ok=True)
        renderer = Renderer(fly.model, [SCENE_CAMERA], camera_res=(480, 640),
                            playback_speed=args.playback_speed)

    names = list(groups)
    spikes = np.zeros((args.ticks, len(names)), np.int64)
    network = np.zeros(args.ticks, np.int64)
    height = np.zeros(args.ticks, np.float64)
    pose = np.zeros((args.ticks, 13), np.float64)
    contacts = np.zeros(args.ticks, np.int64)
    frozen_light = None
    started = time.time()

    for tick in range(args.ticks):
        # Constant-velocity descent. Real looming is characterised by angular
        # size and its rate of expansion; a constant closing speed gives the
        # accelerating angular expansion that looming detectors respond to.
        frac = tick / max(1, args.ticks - 1)
        z = args.start_mm + frac * (args.stop_mm - args.start_mm)
        height[tick] = z
        if fly.swatter_mocap >= 0:
            fly.data.mocap_pos[fly.swatter_mocap] = (0.0, 0.0, z)

        light = mapping(fly.ommatidia())
        if args.condition == "frozen":
            frozen_light = light if frozen_light is None else frozen_light
            light = frozen_light

        stim = [] if args.no_motor else (loop.sense(fly) or [])
        if lamina_src is not None:
            cells, flat, offsets, per = lamina_src
            sums = np.add.reduceat(np.asarray(light)[flat], offsets[:-1])
            mean_lum = sums / per
            # Centre on this frame's own mean so the drive encodes contrast
            # rather than absolute level, then scale to the peak current. A
            # dark object overhead drives its cells negative, which is what a
            # lamina monopolar cell does to a light decrement.
            # Centre on the *adapted operating point*, not on this frame's own
            # mean, and scale by a fixed constant. Scaling by the frame's own
            # max normalises the stimulus away: a frame containing a big dark
            # object gets divided by a bigger number, so the object's own
            # contribution cancels. That bug made a swatter-free control fire
            # harder than the swatter arm.
            centred = mean_lum - args.lamina_reference
            stim = list(stim) + [(cells, (args.inject_lamina * centred
                                          / args.lamina_scale).astype(np.float32))]
        counts, _ = brain.step(light, duration_ms, stimulation=stim or None)
        counts = np.asarray(counts)
        network[tick] = int(counts.sum())
        for j, name in enumerate(names):
            spikes[tick, j] = int(counts[groups[name]].sum())

        if not args.no_motor:
            loop.act(counts, fly, duration_ms / 1000.0)
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

    if renderer is not None:
        renderer.save_video(Path(args.video))
        renderer.close()

    out = Path(args.out or ROOT / f"outputs/swat/{args.condition}.npz")
    out.parent.mkdir(parents=True, exist_ok=True)
    half = args.ticks // 2
    meta = {
        "experiment": "swat",
        "condition": args.condition,
        "no_motor": args.no_motor,
        "inject_lamina": args.inject_lamina,
        "ticks": args.ticks,
        "start_mm": args.start_mm,
        "stop_mm": args.stop_mm,
        "populations": names,
        "spikes_total": {n: int(spikes[:, j].sum()) for j, n in enumerate(names)},
        "spikes_first_half": {n: int(spikes[:half, j].sum()) for j, n in enumerate(names)},
        "spikes_second_half": {n: int(spikes[half:, j].sum()) for j, n in enumerate(names)},
        "mean_network_spikes": float(network.mean()),
        "thorax_displacement_mm": round(float(np.linalg.norm(
            np.asarray(fly.data.xpos[1], float) - start_xyz)), 4),
        "max_height_mm": round(float(pose[:, 2].max()), 4),
        "contacts_mean": float(contacts.mean()),
        "contacts_min": int(contacts.min()),
        "video": args.video,
        "wall_seconds": round(time.time() - started, 1),
    }
    np.savez_compressed(out, spikes=spikes, network_spikes=network,
                        swatter_height=height, pose=pose, contacts=contacts,
                        populations=np.array(names))
    out.with_suffix(".json").write_text(json.dumps(meta, indent=2) + "\n")
    print(json.dumps(meta, indent=2))


if __name__ == "__main__":
    main()
