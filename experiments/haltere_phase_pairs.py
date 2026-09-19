"""Drive two haltere groups sinusoidally, in phase and out of phase.

This is the antagonist-pair question restated in the currency the biology
actually uses. A pitch rotation loads both halteres *in phase*; roll and yaw
load them in *antiphase*. The earlier DC sweep asked the same thing with a
static sign on each group and found nothing, but a static sign is not what a
beating haltere produces -- Coriolis force reverses every half stroke, so the
left/right relationship is a phase relationship, not a sign.

For each pair of groups (A, B), both are driven at the same frequency with a
relative phase offset:

    A:  baseline + depth * sin(2*pi*f*t)
    B:  baseline + depth * sin(2*pi*f*t + phi)

phi = 0 is the pitch-like drive, phi = pi the roll/yaw-like one, and phi = pi/2
a quadrature control that should sit between them if the readout is genuinely
phase-sensitive rather than just sign-sensitive.

Run at two frequencies on purpose. 10 Hz is a **positive control**: the
modulation transfer function shows the pathway follows there, so if in-phase and
antiphase are ever going to differ, they must differ at 10 Hz. 218 Hz is the
wingbeat and the actual question. A difference at 10 Hz with none at 218 Hz is
the expected outcome given a corner near 8 Hz, and it is only interpretable
*because* the low-frequency control works.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WINGBEAT_HZ = 218.0
BASELINE_MV = 12.0
DEPTH_MV = 4.0

PHASES = {"in_phase": 0.0, "quadrature": np.pi / 2, "antiphase": np.pi}


def run(*, dataset="malecns_v1", frequencies=(10.0, 218.0), baseline=BASELINE_MV,
        depth=DEPTH_MV, bin_ms=0.5, duration_ms=1000.0,
        out=ROOT / "outputs/haltere_phase_pairs.json") -> dict:
    from connectome_sim.native import NativeBrain
    from connectome_sim.physiology.common import annotations

    from experiments.haltere_axis_pairs import _clusters, _readouts, _reset
    from experiments.haltere_mtf import null_distribution, vector_strength

    brain = NativeBrain(str(ROOT / "outputs/connectome_sim" / dataset / "graph.npz"))
    ann = annotations(brain.ids)
    groups = _readouts(ann)
    motor = np.concatenate(list(groups.values()))
    clusters = _clusters(ann)
    hal = np.flatnonzero((ann.subclass == "haltere").to_numpy())
    side = ann.rootSide.to_numpy()
    dark = np.zeros(len(brain.retina), dtype=np.float32)

    # Bilateral pairs first: this is the pitch-vs-roll decomposition. Then the
    # two potent clusters against each other, since they are the only ones that
    # move the motor pool at all.
    pairs = {
        "allHaltere_L|R": (hal[side[hal] == "L"].astype(np.int32),
                           hal[side[hal] == "R"].astype(np.int32)),
        "SNpp12_L|R": (clusters["SNpp12"][0], clusters["SNpp12"][1]),
        "SNpp23_L|R": (clusters["SNpp23"][0], clusters["SNpp23"][1]),
        "SNpp12|SNpp23": (np.concatenate(clusters["SNpp12"]).astype(np.int32),
                          np.concatenate(clusters["SNpp23"]).astype(np.int32)),
    }

    n_bins = int(round(duration_ms / bin_ms))
    t_s = (np.arange(n_bins) + 0.5) * bin_ms / 1000.0
    started, results = time.time(), []

    for f in frequencies:
        for pair_name, (a_idx, b_idx) in pairs.items():
            for phase_name, phi in PHASES.items():
                _reset(brain)
                pooled = np.zeros(n_bins)
                per_group = {k: np.zeros(n_bins) for k in groups}
                for k in range(n_bins):
                    wa = baseline + depth * np.sin(2 * np.pi * f * t_s[k])
                    wb = baseline + depth * np.sin(2 * np.pi * f * t_s[k] + phi)
                    c, _ = brain.step(dark, bin_ms, stimulation=[
                        (a_idx, float(wa)), (b_idx, float(wb))])
                    pooled[k] = c[motor].sum()
                    for name, idx in groups.items():
                        per_group[name][k] = c[idx].sum()
                r = vector_strength(pooled, t_s, f)
                mu, sd, _ = null_distribution(pooled, t_s, f)
                sym, anti = _decompose(per_group, groups)
                results.append({
                    "frequency_hz": f, "pair": pair_name, "phase": phase_name,
                    "phase_rad": round(phi, 4),
                    "total_spikes": float(pooled.sum()),
                    "vector_strength": round(r, 5),
                    "z_vs_null": round((r - mu) / sd, 2) if sd else None,
                    # Total drive is identical across phases, so a difference in
                    # spike count is a phase effect and nothing else.
                    "symmetric_power": round(sym, 4),
                    "antisymmetric_power": round(anti, 4),
                    "per_group_spikes": {k: float(v.sum()) for k, v in per_group.items()},
                })
                x = results[-1]
                print(f"{f:6.0f}Hz {pair_name:16s} {phase_name:11s} "
                      f"spikes={x['total_spikes']:7.0f} r={r:.4f} "
                      f"z={str(x['z_vs_null']):>7s} sym={sym:.3f}", flush=True)

    report = {
        "dataset": dataset, "baseline_mV": baseline, "depth_mV": depth,
        "bin_ms": bin_ms, "duration_ms": duration_ms, "wingbeat_hz": WINGBEAT_HZ,
        "phases": {k: round(v, 4) for k, v in PHASES.items()},
        "trials": results,
        "wall_seconds": round(time.time() - started, 1),
    }
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report


def _decompose(per_group, groups):
    """Fraction of response power that is bilaterally symmetric vs antisymmetric."""
    muscles = sorted({k.rsplit("_", 1)[0] for k in groups})
    l = np.array([per_group[f"{m}_L"].sum() for m in muscles])
    r = np.array([per_group[f"{m}_R"].sum() for m in muscles])
    s, d = (l + r) / np.sqrt(2), (l - r) / np.sqrt(2)
    tot = float(s @ s + d @ d)
    return (float(s @ s / tot), float(d @ d / tot)) if tot else (0.0, 0.0)


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--frequencies", type=float, nargs="+", default=[10.0, 218.0])
    p.add_argument("--duration-ms", type=float, default=1000.0)
    p.add_argument("--out", default=str(ROOT / "outputs/haltere_phase_pairs.json"))
    a = p.parse_args()
    r = run(frequencies=a.frequencies, duration_ms=a.duration_ms, out=a.out)
    print(f"\n{len(r['trials'])} trials in {r['wall_seconds']} s -> {a.out}")
