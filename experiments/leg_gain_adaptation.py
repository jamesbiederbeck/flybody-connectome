"""Does network-wide spike-frequency adaptation give the leg loop a graded
walking regime, or does it just kill the same attractor E-GAIN already found?

Context: leg_gain_threshold.py found the leg loop's own drive gain
(proprioceptive_gain/tactile_gain) is a step function -- 0.8x of default
(4.8/6.4) leaves cb_intrinsic at exactly 0 Hz, 0.9x (5.4/7.2) is already at
29.27 of the 32.06 Hz saturated ceiling. There is no intermediate walking
regime along that axis (connectome-lab/findings/09-the-latch-is-the-mushroom-body.md,
"Related" section).

flappy-haltere's E-GAIN class (flappy/run_gain.py) already asked the same
question about the underlying attractor -- does widening spike-frequency
adaptation from Kenyon-cell-only to all 166,700 cells remove the
self-sustaining saturated state -- and found no, not at any strength from
0.125 to 16 mV. But that test drove the network with a single k=4-cell,
current-12 pulse (LLPC1, the weakest drive point E-VIS-INV found), and its own
write-up says plainly: "the drive point was LLPC1 at k=4, the weakest found.
The claim is that adaptation kills the weakest drive at any strength, not
that adaptation and drive cannot coexist. A strong-drive arm is untested."

The leg loop's default gains (6.0/8.0) are exactly that untested strong-drive
arm: continuous, tonic, population-scale (up to ~1,367 real leg afferents
across 6 legs x 2 sensory classes, not a single k=4 pulse), and known to
reliably saturate cb_intrinsic. This script reruns E-GAIN's adaptation sweep
with the leg loop's own drive as the trigger instead of a k=4 pulse. Leg
gains are held fixed at default (6.0/8.0) throughout -- this sweeps
adaptation_jump, not sensory gain -- so a graded response here would mean the
usable knob is adaptation strength inside the network, not afferent gain
upstream of it.

Two questions, same as E-GAIN:

  Does some intermediate adaptation strength turn the leg loop's binary
  switch into a graded walking response (nonzero but bounded cb_intrinsic
  and displacement during drive, rather than either 0 or ~32 Hz)?

  Does adaptation strong enough to break the release-phase latch (cb_intrinsic
  coming back down after leg-sensory stimulation is cut) also kill the
  driven-phase response outright, the way it did for the k=4 pulse? If so this
  closes the "independently confirm this is a hard limit" half of the question
  -- now for the strong-drive case E-GAIN explicitly left open.

CPU physiology kernel only (MemoryBrain) -- the GPU path has no adaptation.
Per flappy-haltere's own note this backend runs roughly 1s/brain-tick, and
each condition here also carries MuJoCo substeps, so this is slow: budget
several minutes per condition at the defaults below and scale --drive-ticks/
--release-ticks down for a first pass. Requires MUJOCO_GL=egl for headless
rendering, same as leg_gain_threshold.py.
"""
import argparse
import json
import time
from pathlib import Path

import numpy as np

from connectome_sim.physiology.brain import MemoryBrain
from connectome_sim.report import population_report
from fly import body as body_mod, legs as legs_mod, motor as motor_mod
from fly.play import _build_receptor_map

ROOT = Path("/home/victor/code/playground/flybody-connectome")
GRAPH = ROOT / "outputs/connectome_sim/malecns_v1/graph.npz"

JUMPS = [0.0, 0.125, 0.25, 0.5, 1.0, 2.0, 4.0, 8.0, 16.0]
DEFAULT_PROP_GAIN = 6.0
DEFAULT_TACT_GAIN = 8.0


def _adaptation_masks():
    """{'kc': default KC-only mask, 'all': every cell}, without keeping a
    throwaway brain alive -- mirrors flappy-haltere/flappy/run_gain.py."""
    probe = MemoryBrain(str(GRAPH))
    kc_mask = np.asarray(probe.adaptation_mask, dtype=np.uint8).copy()
    wide = np.ones(probe.n, dtype=np.uint8)
    del probe
    return {"kc": kc_mask, "all": wide}


def run_condition(scope, jump, tau, mask, settle_ticks, drive_ticks, release_ticks):
    brain = MemoryBrain(str(GRAPH), adaptation_jump=jump, adaptation_tau=tau,
                         adaptation_mask=mask)
    brain.weights_frozen = True  # isolate adaptation; do not also let plasticity move.
    ids = brain.ids

    fly = body_mod.build(world="flat", spawn_height_mm=2.0)
    mapping = _build_receptor_map(brain, fly, str(GRAPH))
    physics_dt = float(fly.model.opt.timestep)
    brain_hz = 30.0
    duration_ms = 1000.0 / brain_hz
    substeps = max(1, int(round((duration_ms / 1000.0) / physics_dt)))

    for _ in range(settle_ticks * substeps):
        fly.step()

    loop = legs_mod.LegLoop(brain, fly, motor_gain=5.0, seed=20260919,
                            proprioceptive_gain=DEFAULT_PROP_GAIN,
                            tactile_gain=DEFAULT_TACT_GAIN)
    body = motor_mod.BodyMap(brain, fly, gain=5.0)
    start_xyz = np.asarray(fly.data.xpos[1], float).copy()

    drive_counts = np.zeros(brain.n, dtype=np.int64)
    release_counts = np.zeros(brain.n, dtype=np.int64)
    total_ticks = drive_ticks + release_ticks
    started = time.time()
    for t in range(total_ticks):
        driving = t < drive_ticks
        # Release phase cuts leg-sensory injection entirely, same as
        # E-GAIN/E-LATCH's drive-then-release protocol -- the question is
        # whether cb_intrinsic comes back down once the trigger is gone.
        stim = loop.sense(fly) if driving else None
        light = mapping(fly.ommatidia())
        counts, _ = brain.step(light, duration_ms, stimulation=stim)
        counts = np.asarray(counts)
        (drive_counts if driving else release_counts).__iadd__(counts)
        loop.act(counts, fly, duration_ms / 1000.0)
        body.act(counts, fly, duration_ms / 1000.0)
        for _ in range(substeps):
            fly.step()
    end_xyz = np.asarray(fly.data.xpos[1], float)
    displacement = float(np.linalg.norm(end_xyz - start_xyz))

    drive_seconds = drive_ticks * duration_ms / 1000.0
    release_seconds = release_ticks * duration_ms / 1000.0
    drive_report = population_report(ids, drive_counts, drive_seconds * 1000,
                                     by="superclass")
    release_report = (population_report(ids, release_counts, release_seconds * 1000,
                                        by="superclass")
                      if release_ticks else None)

    drive_cb = drive_report["cb_intrinsic"]["mean_hz_per_cell"]
    release_cb = release_report["cb_intrinsic"]["mean_hz_per_cell"] if release_report else None
    return {
        "scope": scope,
        "adaptation_jump_mV": jump,
        "adaptation_tau_ms": tau,
        "adapting_cells": int(mask.sum()),
        "proprioceptive_gain": DEFAULT_PROP_GAIN,
        "tactile_gain": DEFAULT_TACT_GAIN,
        "displacement_mm": round(displacement, 4),
        "drive_cb_intrinsic_hz": drive_cb,
        "release_cb_intrinsic_hz": release_cb,
        "drive_total_hz": drive_report["TOTAL"]["mean_hz_per_cell"],
        "release_total_hz": release_report["TOTAL"]["mean_hz_per_cell"] if release_report else None,
        # Latched: activity that should have died with the trigger removed
        # is still present -- same criterion E-LATCH/E-GAIN use.
        "latched": bool(release_cb is not None and release_cb > 0.0),
        "wall_s": round(time.time() - started, 1),
    }


def main():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--jumps", type=float, nargs="+", default=JUMPS)
    p.add_argument("--tau", type=float, default=200.0)
    p.add_argument("--scope", choices=["all", "kc"], nargs="+", default=["all"])
    p.add_argument("--settle-ticks", type=int, default=60)
    p.add_argument("--drive-ticks", type=int, default=100)
    p.add_argument("--release-ticks", type=int, default=100)
    p.add_argument("--out", default=str(Path("/home/victor/code/playground/connectome-lab")
                                        / "leg-gain-adaptation-sweep.json"))
    args = p.parse_args()

    masks = _adaptation_masks()
    results = []
    for scope in args.scope:
        mask = masks[scope]
        for jump in args.jumps:
            r = run_condition(scope, jump, args.tau, mask,
                              args.settle_ticks, args.drive_ticks, args.release_ticks)
            results.append(r)
            print(json.dumps(r), flush=True)

    out = Path(args.out)
    out.write_text(json.dumps(results, indent=2))
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
