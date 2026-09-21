"""Experiment: fire the giant fibre and see whether the fly leaves the ground.

E-GF in the sibling repo established that injecting current into DNp01, the
giant fibre, recruits TTM -- the tergotrochanteral motor neuron that drives the
jump -- but only once DNp01 reaches about 6.5 spikes per tick, which takes an
injected current near 20. That was measured on spikes alone. Whether the body
actually moves is a different question, and this is the harness that can ask it.

TTM is mapped to the middle leg's trochanter-femur extension (see `fly.motor`),
which is the joint the real muscle acts on. That mapping is inferred from the
muscle's name and known action and is not measured here.

Conditions: a current sweep on DNp01, against an uninjected control. The
measurement is body height and vertical velocity, not spikes.
"""
from __future__ import annotations

import argparse, json, time
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ticks", type=int, default=120)
    p.add_argument("--settle-ticks", type=int, default=60)
    p.add_argument("--currents", type=float, nargs="+", default=[0., 20., 40.])
    p.add_argument("--fire-at", type=int, default=30, help="tick at which injection starts")
    p.add_argument("--leg-sense", action="store_true",
                   help="Let the leg loop inject its sensory current as well. "
                        "Off by default, and deliberately: that injection holds "
                        "the network at ~59k spikes/tick against a ~21k resting "
                        "rate, and in that saturated regime DNp01 is suppressed "
                        "and cannot be fired at all. The motor path stays "
                        "connected either way, so the body can still move.")
    p.add_argument("--motor-gain", type=float, default=5.)
    p.add_argument("--brain-hz", type=float, default=30.)
    p.add_argument("--dataset", default="malecns_v1")
    p.add_argument("--video", default=None)
    p.add_argument("--playback-speed", type=float, default=0.2)
    p.add_argument("--out", default=str(ROOT / "outputs/jump/sweep.json"))
    args = p.parse_args()

    from connectome_sim.native import NativeBrain
    from connectome_sim.physiology.common import annotations
    from fly import body as body_mod, legs as legs_mod, motor as motor_mod
    from fly.play import _build_receptor_map

    graph = ROOT / "outputs/connectome_sim" / args.dataset / "graph.npz"
    brain = NativeBrain(str(graph))
    a = annotations(brain.ids); ty = a.type.fillna("")
    dnp01 = np.flatnonzero((ty == "DNp01").to_numpy()).astype(np.int32)
    ttm = np.flatnonzero(ty.isin(["TTMn", "STTMm"]).to_numpy()).astype(np.int32)

    results = []
    for current in args.currents:
        fly = body_mod.build(world="flat", spawn_height_mm=2.0)
        mapping = _build_receptor_map(brain, fly, graph)
        physics_dt = float(fly.model.opt.timestep)
        duration_ms = 1000. / args.brain_hz
        substeps = max(1, int(round((duration_ms / 1000.) / physics_dt)))
        for _ in range(args.settle_ticks * substeps):
            fly.step()
        loop = legs_mod.LegLoop(brain, fly, motor_gain=args.motor_gain)
        body = motor_mod.BodyMap(brain, fly, gain=args.motor_gain)
        brain.reset() if hasattr(brain, "reset") else None

        renderer = None
        if args.video and current == args.currents[-1]:
            from flygym.rendering import Renderer
            from fly.body import SCENE_CAMERA
            Path(args.video).parent.mkdir(parents=True, exist_ok=True)
            renderer = Renderer(fly.model, [SCENE_CAMERA], camera_res=(480, 640),
                                playback_speed=args.playback_speed)

        z, vz, contacts, ttm_spikes, dn_spikes = [], [], [], 0, 0
        started = time.time()
        for tick in range(args.ticks):
            stim = (loop.sense(fly) or []) if args.leg_sense else []
            if current > 0 and tick >= args.fire_at:
                stim = list(stim) + [(dnp01, current)]
            counts, _ = brain.step(mapping(fly.ommatidia()), duration_ms,
                                   stimulation=stim or None)
            counts = np.asarray(counts)
            ttm_spikes += int(counts[ttm].sum()); dn_spikes += int(counts[dnp01].sum())
            loop.act(counts, fly, duration_ms / 1000.)
            body.act(counts, fly, duration_ms / 1000.)
            for _ in range(substeps):
                fly.step()
                if renderer is not None:
                    renderer.render_as_needed(fly.data)
            z.append(float(fly.data.xpos[1][2]))
            vz.append(float(fly.data.cvel[1][5]))
            contacts.append(int(fly.data.ncon))
        if renderer is not None:
            renderer.save_video(Path(args.video)); renderer.close()

        z = np.array(z); after = slice(args.fire_at, None)
        r = {"current": current, "dnp01_per_tick": round(dn_spikes / args.ticks, 3),
             "ttm_per_tick": round(ttm_spikes / args.ticks, 3),
             "rest_height": round(float(z[:args.fire_at].mean()), 4),
             "peak_height_after": round(float(z[after].max()), 4),
             "rise_mm": round(float(z[after].max() - z[:args.fire_at].mean()), 4),
             "peak_upward_velocity": round(float(np.max(vz[args.fire_at:])), 4),
             "min_contacts_after": int(min(contacts[args.fire_at:])),
             "airborne_ticks": int(sum(1 for c in contacts[args.fire_at:] if c == 0)),
             "wall_seconds": round(time.time() - started, 1)}
        results.append(r)
        print(json.dumps(r), flush=True)
        fly.close() if hasattr(fly, "close") else None

    out = Path(args.out); out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"experiment": "jump", "ticks": args.ticks,
                               "fire_at": args.fire_at, "arms": results}, indent=2) + "\n")


if __name__ == "__main__":
    main()
