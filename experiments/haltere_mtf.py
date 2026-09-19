"""Modulation transfer function of the haltere -> wing motor pathway.

How fast a signal can the pathway follow?  Not "can a brief pulse from rest
cause firing" -- `haltere_impulse.py` answered that (no, below ~20 ms), but from
rest the threshold dominates and the measurement says little about a *running*
fly.  Here the pool is held firing by a sustained supra-threshold baseline and a
sinusoid is added on top, which is the regime a beating haltere actually
produces.  Ongoing activity linearises the threshold, so the question becomes
how much of the modulation survives to the motor pool as a function of its
frequency.

Metric is vector strength (phase locking), standard in auditory and
mechanosensory physiology:

    r(f) = |sum_k c_k exp(2*pi*i*f*t_k)| / sum_k c_k

over motor spike counts c_k in bins at times t_k.  r = 1 is perfect locking to
the modulation, r = 0 none.  Every run is paired with an unmodulated control at
the same baseline, which gives the floor that r must beat -- a finite spike
train has nonzero r by chance, and at high frequencies that floor is what a
"response" would otherwise be confused with.

A wingbeat is 4.59 ms (218 Hz).  If r collapses to the floor well below that,
sub-wingbeat structure does not reach the wing muscles in this model, and the
frequency where it collapses says how far the membrane time constant would have
to fall to change that.
"""

from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WINGBEAT_HZ = 218.0

# Baseline sits above the ~10 mV recruitment threshold measured in
# flappy-haltere's cluster sweep, so the pool is already firing and the
# modulation is a perturbation rather than an on/off switch.
BASELINE_MV = 12.0
DEPTH_MV = 4.0


def vector_strength(counts, t_s, f_hz):
    """Phase locking of a binned spike train to frequency `f_hz`."""
    n = counts.sum()
    if n <= 0:
        return 0.0
    phasor = np.exp(2j * np.pi * f_hz * t_s)
    return float(abs((counts * phasor).sum()) / n)


# Frequencies used to estimate the chance level *within* a trial.  A paired
# control run is not enough: chance vector strength scales as 1/sqrt(N), so a
# single-cell readout with a few dozen spikes has a floor near 0.2 while the
# pooled readout with ~1800 spikes has one near 0.02.  Evaluating the same spike
# train at frequencies it was not driven at gives a floor with the right spike
# count by construction, for every group separately.
NULL_HZ = (3., 7., 13., 23., 41., 67., 97., 149., 211., 293., 397., 499.)


def null_distribution(counts, t_s, f_hz):
    """Chance vector strength for this spike train, away from `f_hz`.

    Excludes anything near the driven frequency or its low harmonics and
    subharmonics, where real modulation power would leak in.
    """
    keep = []
    for g in NULL_HZ:
        if min(abs(g - k * f_hz) / max(k * f_hz, 1.0)
               for k in (0.5, 1.0, 2.0, 3.0)) > 0.15:
            keep.append(vector_strength(counts, t_s, g))
    if not keep:
        return 0.0, 0.0, 0
    return float(np.mean(keep)), float(np.std(keep)), len(keep)


def run(*, dataset="malecns_v1", frequencies=(5, 10, 30, 60, 120, 218, 400),
        baseline=BASELINE_MV, depth=DEPTH_MV, bin_ms=0.5, duration_ms=1000.0,
        out=ROOT / "outputs/haltere_mtf.json") -> dict:
    from connectome_sim.native import NativeBrain
    from connectome_sim.physiology.common import annotations

    from experiments.haltere_axis_pairs import _readouts, _reset

    brain = NativeBrain(str(ROOT / "outputs/connectome_sim" / dataset / "graph.npz"))
    ann = annotations(brain.ids)
    groups = _readouts(ann)
    motor = np.concatenate(list(groups.values()))
    halteres = np.flatnonzero((ann.subclass == "haltere").to_numpy()).astype(np.int32)
    dark = np.zeros(len(brain.retina), dtype=np.float32)

    n_bins = int(round(duration_ms / bin_ms))
    t_s = (np.arange(n_bins) + 0.5) * bin_ms / 1000.0
    started = time.time()

    def trial(f_hz, amplitude):
        _reset(brain)
        counts = np.zeros(n_bins)
        per_group = {k: np.zeros(n_bins) for k in groups}
        for k in range(n_bins):
            drive = baseline + amplitude * np.sin(2 * np.pi * f_hz * t_s[k])
            c, _ = brain.step(dark, bin_ms, stimulation=(halteres, float(drive)))
            counts[k] = c[motor].sum()
            for name, idx in groups.items():
                per_group[name][k] = c[idx].sum()
        return counts, per_group

    def score(counts, f_hz):
        """Vector strength against this train's own chance level.

        z is what to read: how many standard deviations the driven frequency
        stands above what the same spikes give at undriven frequencies.  r alone
        is not comparable between a 1-cell and a 24-cell readout.
        """
        r = vector_strength(counts, t_s, f_hz)
        mu, sd, n = null_distribution(counts, t_s, f_hz)
        return {"r": round(r, 5), "null_mean": round(mu, 5), "null_sd": round(sd, 5),
                "null_n": n, "z": round((r - mu) / sd, 2) if sd else None,
                "spikes": float(counts.sum())}

    results = []
    for f in frequencies:
        mod, mod_groups = trial(f, depth)
        # Unmodulated control at the same baseline and the same duration: its
        # vector strength at f is the floor, set by spike count alone.
        ctl, ctl_groups = trial(f, 0.0)
        pooled = score(mod, f)
        pooled_ctl = score(ctl, f)
        results.append({
            "modulation_hz": f,
            "wingbeats_per_cycle": round(WINGBEAT_HZ / f, 3),
            "pooled": pooled,
            "pooled_unmodulated_control": pooled_ctl,
            # Per group, each with its own chance level and spike count -- the
            # fix for the first run, where a 1-cell readout's r was reported
            # without the floor that makes it interpretable.
            "per_group": {k: score(v, f) for k, v in mod_groups.items()},
            "per_group_control": {k: score(v, f) for k, v in ctl_groups.items()},
        })
        print(f"{f:6.0f} Hz  pooled r={pooled['r']:.4f} z={str(pooled['z']):>6s}  "
              f"(control z={str(pooled_ctl['z']):>6s})  spikes={mod.sum():.0f}", flush=True)

    report = {
        "dataset": dataset, "baseline_mV": baseline, "depth_mV": depth,
        "bin_ms": bin_ms, "duration_ms": duration_ms,
        "wingbeat_hz": WINGBEAT_HZ,
        "metric": "vector strength of binned wing-motor spikes at the modulation "
                  "frequency, scored as z against the same train's vector strength "
                  "at undriven frequencies",
        "null_frequencies_hz": list(NULL_HZ),
        "frequencies": results,
        "wall_seconds": round(time.time() - started, 1),
    }
    out = Path(out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--frequencies", type=float, nargs="+",
                   default=[5, 10, 30, 60, 120, 218, 400])
    p.add_argument("--baseline", type=float, default=BASELINE_MV)
    p.add_argument("--depth", type=float, default=DEPTH_MV)
    p.add_argument("--bin-ms", type=float, default=0.5)
    p.add_argument("--duration-ms", type=float, default=1000.0)
    p.add_argument("--out", default=str(ROOT / "outputs/haltere_mtf.json"))
    a = p.parse_args()
    r = run(frequencies=a.frequencies, baseline=a.baseline, depth=a.depth,
            bin_ms=a.bin_ms, duration_ms=a.duration_ms, out=a.out)
    print(f"\n{len(r['frequencies'])} frequencies in {r['wall_seconds']} s -> {a.out}")
