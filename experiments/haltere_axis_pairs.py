"""Antagonist-pair search over haltere afferent clusters.

For each candidate pair of bilateral haltere types (A, B), drive the four groups
L-A, L-B, R-A, R-B at a tonic baseline +/- delta in four sign conditions, and
record the wing motor response.

    1  L-A+ L-B- R-A+ R-B-   symmetric
    2  L-A+ L-B- R-A- R-B+   antisymmetric
    3  L-A- L-B+ R-A+ R-B-   antisymmetric (negation of 2)
    4  L-A- L-B+ R-A- R-B+   symmetric (negation of 1)

DC drive, not modulated at wingbeat frequency: the engine's 20 ms membrane and
5 ms synaptic constants low-pass a 218 Hz modulation to ~3.6% before it leaves
the afferent, so a phase or duty-cycle code cannot be tested here.  See
`docs/haltere-axis-mapping-experiments.md` in flappy-haltere.

State is reset between conditions rather than reloading the graph, and the reset
is *verified* rather than assumed: condition 1 is re-run at the end of every pair
and must reproduce its first result exactly.
"""

from __future__ import annotations

import argparse
import itertools
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]

# Motor-side selection follows flappy-haltere's `flappy/fly_regions.py`, which
# is the module that already worked this out: `vnc_motor` cells carry no
# `rootSide` at all (NaN for all 708), so side comes from the `_L`/`_R` suffix
# on `instance`.  Selecting on rootSide silently returns nothing.
STEERING_TYPES = ["b1 MN", "b2 MN", "hg1 MN"]
POWER_TYPES = ["DLMn a, b", "DLMn c-f", "DVMn 1a-c", "DVMn 2a, b", "DVMn 3a, b"]

# flappy-haltere measured that a ~50 ms pulse from a cold start mostly produces
# silence (9/10 trials fired zero wing-muscle spikes); the haltere->flight-motor
# reflex is a sharp-threshold, *sustained*-drive circuit and its working config
# holds current for 500 ms.  Anything shorter here measures the threshold, not
# the pairing.
SUSTAIN_MS = 500.0
# Current range validated by the same work (4-14 mV); baseline +/- delta stays
# inside it.
# Both levels must sit above the reflex's threshold, or a condition is not
# "drive B less", it is "do not drive B at all", and the four conditions stop
# being a sign flip of each other.
BASELINE_MV = 11.0
DELTA_MV = 3.0

# Sign pattern per condition, ordered (L-A, L-B, R-A, R-B).
CONDITIONS = {
    "1_sym": (+1, -1, +1, -1),
    "2_anti": (+1, -1, -1, +1),
    "3_anti_neg": (-1, +1, +1, -1),
    "4_sym_neg": (-1, +1, -1, +1),
}


def _reset(brain) -> None:
    """Restore exactly the state `Brain.__init__` leaves behind."""
    brain.v.fill(-52); brain.g.fill(0); brain.drive.fill(0)
    brain.refractory.fill(0); brain.queue.fill(0); brain.queue_count.fill(0)
    brain.counts.fill(0); brain.luminance.fill(0)
    brain.active.fill(0); brain.active_flag.fill(0)
    initial = np.unique(np.r_[brain.retina, brain.lamina, brain.sugar])
    brain.active[:len(initial)] = initial
    brain.active_flag[initial] = 1
    brain.nactive[0] = len(initial)
    brain.cursor = 0
    brain.total_spikes = 0
    brain.sim_ms = 0
    if hasattr(brain, "previous_drive"):
        brain.previous_drive.fill(0)
    if hasattr(brain, "last"):
        brain.last.fill(-1)


def _clusters(ann):
    """Bilateral haltere types, excluding the undifferentiated SApp bulk.

    SApp is 148 of the 205 afferents in one undifferentiated type and is the
    only preliminarily-traced group; the ten named SNpp*/SNxx* types are
    Reviewed and near-perfectly symmetric L/R, so a type *is* a bilateral pair.
    """
    hal = (ann.subclass == "haltere").to_numpy()
    types = ann.type.to_numpy()
    side = ann.rootSide.to_numpy()
    out = {}
    for t in sorted({t for t, h in zip(types, hal) if h and isinstance(t, str) and t != "SApp"}):
        left = np.flatnonzero(hal & (types == t) & (side == "L")).astype(np.int32)
        right = np.flatnonzero(hal & (types == t) & (side == "R")).astype(np.int32)
        if len(left) and len(right):
            out[t] = (left, right)
    return out


def _side_of(instance):
    if not isinstance(instance, str):
        return None
    return instance[-1] if instance.endswith(("_L", "_R")) else None


def _readouts(ann):
    """Wing motor groups, split by side: the response vector's coordinates."""
    motor = (ann.superclass.astype(str) == "vnc_motor").to_numpy()
    types = ann.type.to_numpy()
    side = np.array([_side_of(i) for i in ann.instance.to_numpy()])
    groups = {}
    for label, wanted in [("b1", ["b1 MN"]), ("b2", ["b2 MN"]),
                          ("hg1", ["hg1 MN"]), ("power", POWER_TYPES)]:
        for s in ("L", "R"):
            idx = np.flatnonzero(motor & np.isin(types, wanted) & (side == s))
            groups[f"{label}_{s}"] = idx.astype(np.int32)
    empty = [k for k, v in groups.items() if not len(v)]
    if empty:
        raise ValueError(f"Empty motor readout groups: {empty}")
    return groups


def _response(brain, dark, groups, stim, duration_ms):
    _reset(brain)
    counts, _ = brain.step(dark, duration_ms, stimulation=stim)
    return np.array([float(counts[idx].sum()) for idx in groups.values()])


def run(*, dataset="malecns_v1", baseline=BASELINE_MV, delta=DELTA_MV,
        duration_ms=SUSTAIN_MS, limit=None,
        out=ROOT / "outputs/haltere_axis_pairs.json") -> dict:
    from connectome_sim.native import NativeBrain
    from connectome_sim.physiology.common import annotations

    graph = ROOT / "outputs/connectome_sim" / dataset / "graph.npz"
    brain = NativeBrain(str(graph))
    ann = annotations(brain.ids)
    clusters = _clusters(ann)
    groups = _readouts(ann)
    dark = np.zeros(len(brain.retina), dtype=np.float32)

    names = sorted(clusters)
    coords = list(groups)
    # Symmetric / antisymmetric projection over the L,R pair of each muscle.
    muscles = sorted({c.rsplit("_", 1)[0] for c in coords})
    li = [coords.index(f"{m}_L") for m in muscles]
    ri = [coords.index(f"{m}_R") for m in muscles]

    pairs = list(itertools.combinations(names, 2))
    if limit:
        pairs = pairs[:limit]
    results, started = [], time.time()
    for a_name, b_name in pairs:
        (la, ra), (lb, rb) = clusters[a_name], clusters[b_name]
        # Spike counts are non-negative, so responses must be expressed as
        # deviations from a common reference before any sign-inversion test
        # means anything: between two non-negative vectors cos() can never be
        # negative, and cos(r1, -r4) would only be measuring whether the two
        # responses are parallel.  The reference is all four groups at the
        # baseline current, i.e. the same total drive with no asymmetry.
        ref = _response(brain, dark, groups,
                        [(la, baseline), (lb, baseline),
                         (ra, baseline), (rb, baseline)], duration_ms)
        resp, check = {}, None
        for label, signs in CONDITIONS.items():
            stim = [(la, baseline + signs[0] * delta),
                    (lb, baseline + signs[1] * delta),
                    (ra, baseline + signs[2] * delta),
                    (rb, baseline + signs[3] * delta)]
            resp[label] = _response(brain, dark, groups, stim, duration_ms) - ref
        # Re-run condition 1; the reset is only trustworthy if this matches.
        signs = CONDITIONS["1_sym"]
        check = _response(brain, dark, groups, [
            (la, baseline + signs[0] * delta), (lb, baseline + signs[1] * delta),
            (ra, baseline + signs[2] * delta), (rb, baseline + signs[3] * delta)],
            duration_ms) - ref
        if not np.array_equal(check, resp["1_sym"]):
            raise RuntimeError(
                f"State reset is not clean: {a_name}/{b_name} condition 1 did not "
                f"reproduce ({resp['1_sym']} then {check}). Every result in this "
                "run is suspect.")

        r = {k: v for k, v in resp.items()}
        results.append({
            "pair": [a_name, b_name],
            "reference_response": ref.tolist(),
            "response": {k: v.tolist() for k, v in r.items()},
            "sign_inversion_sym": _cos(r["1_sym"], -r["4_sym_neg"]),
            "sign_inversion_anti": _cos(r["2_anti"], -r["3_anti_neg"]),
            "symmetry": {k: _symmetry(v, li, ri) for k, v in r.items()},
            "total_spikes": {k: float(v.sum()) for k, v in r.items()},
        })
        print(f"{a_name:8s} {b_name:8s} "
              f"inv_sym={results[-1]['sign_inversion_sym']:+.3f} "
              f"inv_anti={results[-1]['sign_inversion_anti']:+.3f} "
              f"sym1={results[-1]['symmetry']['1_sym']:.3f} "
              f"sym2={results[-1]['symmetry']['2_anti']:.3f}", flush=True)

    report = {
        "dataset": dataset,
        "baseline_current": baseline,
        "delta_current": delta,
        "duration_ms": duration_ms,
        "drive": "DC (engine cannot carry a 218 Hz modulation; see module docstring)",
        "clusters": {k: [len(v[0]), len(v[1])] for k, v in clusters.items()},
        "readout_coordinates": coords,
        "pairs": results,
        "wall_seconds": round(time.time() - started, 1),
    }
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report


def _cos(a, b):
    na, nb = np.linalg.norm(a), np.linalg.norm(b)
    return float(a @ b / (na * nb)) if na and nb else 0.0


def _symmetry(v, li, ri):
    """Fraction of response power in the symmetric (L+R) subspace.

    1.0 is purely symmetric, 0.0 purely antisymmetric. A correct pairing should
    put conditions 1/4 high and 2/3 low; cross-talk is the quantitative form of
    'the brain reads it as a twist rather than a rotation'.
    """
    s = (v[li] + v[ri]) / np.sqrt(2)
    d = (v[li] - v[ri]) / np.sqrt(2)
    p = float(s @ s + d @ d)
    return float(s @ s / p) if p else 0.0


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--baseline", type=float, default=BASELINE_MV)
    p.add_argument("--delta", type=float, default=DELTA_MV)
    p.add_argument("--duration-ms", type=float, default=SUSTAIN_MS)
    p.add_argument("--limit", type=int, default=None, help="first N pairs only")
    p.add_argument("--out", default=str(ROOT / "outputs/haltere_axis_pairs.json"))
    a = p.parse_args()
    r = run(baseline=a.baseline, delta=a.delta, duration_ms=a.duration_ms,
            limit=a.limit, out=a.out)
    print(f"\n{len(r['pairs'])} pairs, {r['wall_seconds']} s -> {a.out}")
