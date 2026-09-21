"""Does a fixed scent source bias net walking direction? (`fly/legs.py` + olfaction)

**Question.** The leg loop (`fly/legs.py`, `fly/walk.py`) closes ground-contact
and joint-angle sensing onto leg motor neurons -- see the 2026-09-20 LOG entry
"A closed leg loop, and a control that cut the wrong half". This experiment
layers one more sensory channel onto the same stimulation list: a fixed
point-source scent, injected into the ORN_DA1 olfactory population, split
left/right by which side of the fly's midline the source sits on. Question:
does the fly's *net walking direction* end up biased toward or away from the
source, or is any effect indistinguishable from this connectome's own
two-state (quiescent / generically saturated) dynamics?

**Invented choices, stated plainly:**

- **Glomerulus: ORN_DA1.** One of ~50 glomerulus types with mapped ORN
  populations in the MaleCNS annotations (204 cells total: 105 R / 51 L / 48
  `rootSide == "unknown"`, matching `instance`'s `_R`/`_L`/no-suffix split
  exactly). Chosen arbitrarily among the available glomeruli -- this is not a
  claim about what odor DA1 encodes biologically, just a real, specific ORN
  population to drive. The 48 unknown-laterality cells are excluded from the
  directional injection entirely (they cannot be assigned a side); only the
  156 sided cells (105 R, 51 L) receive current.
- **Falloff: exponential**, `exp(-distance / 10mm)`, invented because it is the
  simplest function with the right qualitative shape (near = strong, far = weak,
  no discontinuity) and a length scale of the same order as the leg loop's own
  displacement scale, not because anything about ORN transduction is measured
  here.
- **L/R split by lateral position**, not by concentration difference at two
  physical nostril-like points (the fly has no such sensor pair in this model):
  intensity is divided between the R and L ORN_DA1 pools by the cosine of the
  bearing to the source against the fly's own right-axis, so a source dead
  ahead splits 50/50 and a source abeam one side sends (almost) everything to
  that side's population. This is an engineered proxy for "which side smells it
  more", not a measurement of glomerular convergence.
- **Olfactory gain 8.0 mV**, same order as `fly.legs`'s own tactile gain, chosen
  to be large enough to matter against the ORN rheobase and otherwise
  unfitted.

**Heading.** The fly's local forward/right axes are taken as +y/+x rotated by
the thorax quaternion (`fly.body`'s own scene-camera comment records the
convention: "+y forward, +z up"), via `mujoco.mju_rotVecQuat`. No new
orientation math beyond what the camera placement already assumes.

**Not attempted.** No scent-CRZ "association" is built or simulated. This
project's only plasticity is the fixed 4,184-edge KC->MBON11 pathway
(`connectome-lab/findings/05-plasticity-cannot-reach-the-controller.md`), CRZ is
confirmed separately not to be part of it, and there is no learning mechanism
in this codebase that could produce a real olfactory association -- faking one
host-side would misrepresent what the connectome does.

**Conditions**, each a fresh `NativeBrain` + fresh `fly.body.build()` (this
project's own established convention: reusing brain/body state across
conditions has produced wrong answers before -- see `AGENTS.md` and the
haltere-amplitude entries in this log): scent ahead, scent behind, scent to one
side (right, arbitrary), and no-scent (leg loop only, identical to this
session's own leg-loop characterization run: 200 ticks, 60 settle, motor-gain
5, brain-hz 30).

**Metrics.** Net thorax displacement projected onto the fly-to-scent bearing at
trial start (positive = moved toward the source, negative = away, computed
once the trial starts so it is not defined by an already-changing target); and
`cb_intrinsic` mean Hz/cell (`connectome_sim.report.population_report`), the
signature this project uses to tell whether a run entered the generic
saturated attractor (~32-33 Hz/cell) or stayed below it.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

GLOMERULUS = "ORN_DA1"          # invented: arbitrary choice among ~50 glomeruli
FALLOFF_LENGTH_MM = 10.0        # invented exponential length scale
OLFACTORY_GAIN_MV = 8.0         # invented, same order as fly.legs' tactile_gain

# Offsets from the fly's start position, world frame == fly-local frame at
# spawn (neutral quaternion). Distance is ~2x the ~6.7mm/200-tick displacement
# this session's leg-loop characterization measured at motor-gain 5 -- within
# reach, not absurdly far or near.
SCENT_DISTANCE_MM = 15.0
CONDITION_OFFSETS = {
    "ahead": np.array([0.0, SCENT_DISTANCE_MM, 0.0]),
    "behind": np.array([0.0, -SCENT_DISTANCE_MM, 0.0]),
    "side": np.array([SCENT_DISTANCE_MM, 0.0, 0.0]),   # to the fly's right; arbitrary
    "none": None,
}


def orn_da1_sides(brain):
    """(idx_l, idx_r, n_unknown) for ORN_DA1 by `rootSide`."""
    from connectome_sim.physiology.common import annotations
    a = annotations(brain.ids)
    mask = (a.type == GLOMERULUS).to_numpy()
    side = a.rootSide
    idx_l = np.flatnonzero(mask & (side == "L").to_numpy()).astype(np.int32)
    idx_r = np.flatnonzero(mask & (side == "R").to_numpy()).astype(np.int32)
    n_unknown = int((mask & (side == "unknown").to_numpy()).sum())
    return idx_l, idx_r, n_unknown


def scent_stim(fly, source_xyz, idx_l, idx_r, *, gain_mv, falloff_length_mm,
               thorax_body=1, symmetric_split=False):
    """Stimulation entries for ORN_DA1-R/L given the fly's current pose.

    `symmetric_split=True` is the specificity control: same total intensity
    and the same distance time-course, but always split 50/50 L/R, removing
    the only piece of directional information the injection carries. Same
    shape as `experiments/jo_specificity_control.py`'s "is this response
    specific, or would any perturbation of this size do the same thing"
    question.
    """
    import mujoco as mj
    d = fly.data
    pos = np.asarray(d.xpos[thorax_body], float)
    quat = np.asarray(d.xquat[thorax_body], float)
    to_source = source_xyz - pos
    distance = float(np.linalg.norm(to_source))
    if distance < 1e-9:
        return [], distance, 0.0
    unit = to_source / distance
    forward_world = np.zeros(3)
    right_world = np.zeros(3)
    mj.mju_rotVecQuat(forward_world, np.array([0.0, 1.0, 0.0]), quat)
    mj.mju_rotVecQuat(right_world, np.array([1.0, 0.0, 0.0]), quat)
    lateral = float(np.clip(np.dot(unit, right_world), -1.0, 1.0))
    intensity = gain_mv * float(np.exp(-distance / falloff_length_mm))
    if symmetric_split:
        right_frac = 0.5
    else:
        right_frac = 0.5 + 0.5 * lateral
    left_frac = 1.0 - right_frac
    stim = []
    if len(idx_r) and intensity * right_frac > 0:
        stim.append((idx_r, float(intensity * right_frac)))
    if len(idx_l) and intensity * left_frac > 0:
        stim.append((idx_l, float(intensity * left_frac)))
    return stim, distance, lateral


def run_condition(name, *, ticks, settle_ticks, dataset, brain_hz, spawn_height_mm,
                  proprioceptive_gain, tactile_gain, motor_gain, seed,
                  olfactory_gain_mv=OLFACTORY_GAIN_MV,
                  falloff_length_mm=FALLOFF_LENGTH_MM,
                  scent_distance_mm=SCENT_DISTANCE_MM,
                  symmetric_split=False):
    from connectome_sim.native import NativeBrain
    from connectome_sim.report import population_report
    from fly import body as body_mod
    from fly import legs as legs_mod
    from fly.play import _build_receptor_map

    graph = ROOT / "outputs/connectome_sim" / dataset / "graph.npz"
    brain = NativeBrain(str(graph))
    fly = body_mod.build(world="flat", spawn_height_mm=spawn_height_mm)
    mapping = _build_receptor_map(brain, fly, graph)
    idx_l, idx_r, n_unknown = orn_da1_sides(brain)

    physics_dt = float(fly.model.opt.timestep)
    duration_ms = 1000.0 / brain_hz
    substeps = max(1, int(round((duration_ms / 1000.0) / physics_dt)))
    for _ in range(settle_ticks * substeps):
        fly.step()

    loop = legs_mod.LegLoop(brain, fly, proprioceptive_gain=proprioceptive_gain,
                            tactile_gain=tactile_gain, motor_gain=motor_gain, seed=seed)
    start_xyz = np.asarray(fly.data.xpos[1], float).copy()
    offset = CONDITION_OFFSETS[name]
    if offset is not None:
        offset = offset / np.linalg.norm(offset) * scent_distance_mm
    source_xyz = start_xyz + offset if offset is not None else None
    bearing_unit = (offset / np.linalg.norm(offset)) if offset is not None else None

    sum_counts = np.zeros(len(brain.ids), np.float64)
    distances, laterals = [], []
    started = time.time()
    for _tick in range(ticks):
        leg_stim = loop.sense(fly)
        combined = list(leg_stim) if leg_stim else []
        if source_xyz is not None:
            scent_list, distance, lateral = scent_stim(
                fly, source_xyz, idx_l, idx_r, gain_mv=olfactory_gain_mv,
                falloff_length_mm=falloff_length_mm, symmetric_split=symmetric_split)
            combined += scent_list
            distances.append(distance)
            laterals.append(lateral)
        stim = combined or None

        light = mapping(fly.ommatidia())
        counts, _ = brain.step(light, duration_ms, stimulation=stim)
        counts = np.asarray(counts)
        sum_counts += counts

        loop.act(counts, fly, duration_ms / 1000.0)
        for _ in range(substeps):
            fly.step()

    end_xyz = np.asarray(fly.data.xpos[1], float).copy()
    displacement_vec = end_xyz - start_xyz
    displacement_mm = float(np.linalg.norm(displacement_vec))
    toward_mm = (float(np.dot(displacement_vec, bearing_unit))
                if bearing_unit is not None else None)

    total_duration_ms = ticks * duration_ms
    report = population_report(brain.ids, sum_counts, total_duration_ms)
    cb_intrinsic_hz = report["cb_intrinsic"]["mean_hz_per_cell"]

    def orn_hz(idx):
        if len(idx) == 0:
            return 0.0
        return round(float(sum_counts[idx].sum() / len(idx) / (total_duration_ms / 1000.0)), 3)

    return {
        "condition": name,
        "n_orn_da1_l": int(len(idx_l)),
        "n_orn_da1_r": int(len(idx_r)),
        "n_orn_da1_unknown_excluded": n_unknown,
        "source_offset_mm": offset.tolist() if offset is not None else None,
        "displacement_mm": round(displacement_mm, 4),
        "displacement_vec_mm": [round(float(x), 4) for x in displacement_vec],
        "toward_source_mm": round(toward_mm, 4) if toward_mm is not None else None,
        "mean_distance_to_source_mm": (round(float(np.mean(distances)), 3)
                                       if distances else None),
        "mean_lateral": round(float(np.mean(laterals)), 4) if laterals else None,
        "olfactory_gain_mv": olfactory_gain_mv,
        "peak_injected_mv": (round(olfactory_gain_mv
                                   * float(np.exp(-scent_distance_mm / falloff_length_mm)), 3)
                             if offset is not None else 0.0),
        "orn_da1_l_hz_per_cell": orn_hz(idx_l),
        "orn_da1_r_hz_per_cell": orn_hz(idx_r),
        "cb_intrinsic_hz_per_cell": cb_intrinsic_hz,
        "total_spikes": int(sum_counts.sum()),
        "wall_seconds": round(time.time() - started, 1),
    }


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ticks", type=int, default=200)
    p.add_argument("--settle-ticks", type=int, default=60)
    p.add_argument("--dataset", default="malecns_v1")
    p.add_argument("--brain-hz", type=float, default=30.0)
    p.add_argument("--spawn-height-mm", type=float, default=2.0)
    p.add_argument("--proprioceptive-gain", type=float, default=6.0)
    p.add_argument("--tactile-gain", type=float, default=8.0)
    p.add_argument("--motor-gain", type=float, default=5.0)
    p.add_argument("--seed", type=int, default=20260919)
    p.add_argument("--olfactory-gain-mv", type=float, default=OLFACTORY_GAIN_MV)
    p.add_argument("--falloff-length-mm", type=float, default=FALLOFF_LENGTH_MM)
    p.add_argument("--scent-distance-mm", type=float, default=SCENT_DISTANCE_MM)
    p.add_argument("--symmetric-split", action="store_true",
                   help="Specificity control: same intensity/time-course, always "
                        "50/50 L/R -- removes directional information from the "
                        "injection to test whether a delta is generic perturbation.")
    p.add_argument("--conditions", default="ahead,behind,side,none",
                   help="Comma-separated subset of ahead,behind,side,none.")
    p.add_argument("--out", default=str(ROOT / "outputs/scent_taxis/run.json"))
    args = p.parse_args()

    results = {}
    for name in args.conditions.split(","):
        print(f"--- condition: {name} ---")
        results[name] = run_condition(
            name, ticks=args.ticks, settle_ticks=args.settle_ticks,
            dataset=args.dataset, brain_hz=args.brain_hz,
            spawn_height_mm=args.spawn_height_mm,
            proprioceptive_gain=args.proprioceptive_gain,
            tactile_gain=args.tactile_gain, motor_gain=args.motor_gain,
            seed=args.seed, olfactory_gain_mv=args.olfactory_gain_mv,
            falloff_length_mm=args.falloff_length_mm,
            scent_distance_mm=args.scent_distance_mm,
            symmetric_split=args.symmetric_split)
        print(json.dumps(results[name], indent=2))

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({
        "experiment": "scent_taxis",
        "glomerulus": GLOMERULUS,
        "falloff": f"exp(-distance / {args.falloff_length_mm}mm)",
        "olfactory_gain_mv": args.olfactory_gain_mv,
        "scent_distance_mm": args.scent_distance_mm,
        "params": {"ticks": args.ticks, "settle_ticks": args.settle_ticks,
                   "motor_gain": args.motor_gain, "brain_hz": args.brain_hz},
        "results": results,
    }, indent=2) + "\n")
    print(f"Wrote {out}")


if __name__ == "__main__":
    main()
