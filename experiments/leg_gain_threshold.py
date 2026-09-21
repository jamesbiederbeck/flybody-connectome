"""Where does the leg-loop's sensory drive stop and start saturating cb_intrinsic?

fly/legs.py's LegLoop defaults (proprioceptive_gain=6.0, tactile_gain=8.0) drive
the network into the same saturated regime as an isolated SApp/CRZ pulse (see
walk-characterization.json: cb_intrinsic 32.06 Hz/cell). This sweeps both gains
together as a fraction of default to find whether there's a graded regime
between "network fully quiescent" and "network fully saturated," or whether --
consistent with findings/02-two-states.md -- it's a step function.

Each condition uses a fresh NativeBrain and a fresh fly body build (motor_gain=5.0,
200 ticks, 60 settle ticks, matching the existing leg-loop characterization for
comparability). Requires MUJOCO_GL=egl for headless rendering.
"""
import numpy as np, json, time
from pathlib import Path
from connectome_sim.native import NativeBrain
from connectome_sim.report import population_report
from fly import body as body_mod, legs as legs_mod, motor as motor_mod
from fly.play import _build_receptor_map

ROOT = Path("/home/victor/code/playground/flybody-connectome")
GRAPH = ROOT / "outputs/connectome_sim/malecns_v1/graph.npz"


def run_condition(name, prop_gain, tact_gain):
    brain = NativeBrain(str(GRAPH))
    ids = brain.ids
    fly = body_mod.build(world="flat", spawn_height_mm=2.0)
    mapping = _build_receptor_map(brain, fly, GRAPH)
    physics_dt = float(fly.model.opt.timestep)
    brain_hz = 30.0
    duration_ms = 1000.0 / brain_hz
    substeps = max(1, int(round((duration_ms / 1000.0) / physics_dt)))
    settle_ticks, ticks = 60, 200

    for _ in range(settle_ticks * substeps):
        fly.step()

    loop = legs_mod.LegLoop(brain, fly, motor_gain=5.0, seed=20260919,
                            proprioceptive_gain=prop_gain, tactile_gain=tact_gain)
    body = motor_mod.BodyMap(brain, fly, gain=5.0)
    start_xyz = np.asarray(fly.data.xpos[1], float).copy()

    total_counts = np.zeros(brain.n, dtype=np.int64)
    started = time.time()
    for _ in range(ticks):
        stim = loop.sense(fly)
        light = mapping(fly.ommatidia())
        counts, _ = brain.step(light, duration_ms, stimulation=stim)
        counts = np.asarray(counts)
        total_counts += counts
        loop.act(counts, fly, duration_ms / 1000.0)
        body.act(counts, fly, duration_ms / 1000.0)
        for _ in range(substeps):
            fly.step()
    end_xyz = np.asarray(fly.data.xpos[1], float)
    displacement = float(np.linalg.norm(end_xyz - start_xyz))
    total_seconds = ticks * duration_ms / 1000.0
    report = population_report(ids, total_counts, total_seconds * 1000, by="superclass")
    return {"condition": name, "proprioceptive_gain": prop_gain, "tactile_gain": tact_gain,
            "displacement_mm": round(displacement, 4),
            "cb_intrinsic_hz": report["cb_intrinsic"]["mean_hz_per_cell"],
            "total_hz": report["TOTAL"]["mean_hz_per_cell"],
            "wall_s": round(time.time() - started, 1)}


CONDITIONS = [
    ("1.0x_baseline", 6.0, 8.0),
    ("0.9x", 5.4, 7.2),
    ("0.8x", 4.8, 6.4),
    ("0.7x", 4.2, 5.6),
    ("0.6x", 3.6, 4.8),
    ("0.5x", 3.0, 4.0),
    ("0.25x", 1.5, 2.0),
    ("0.1x", 0.6, 0.8),
    ("0.01x", 0.06, 0.08),
]


def main():
    results = [run_condition(*c) for c in CONDITIONS]
    for r in results:
        print(json.dumps(r))
    out = Path("/home/victor/code/playground/connectome-lab/leg-gain-sweep.json")
    out.write_text(json.dumps(results, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
