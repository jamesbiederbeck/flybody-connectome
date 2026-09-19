"""How wide is the motor pool's response to a brief haltere pulse?

The claim this tests is analytic and unverified: a 20 ms membrane should pass
~3.6% of a 218 Hz modulation, so nothing about spike timing within a wingbeat
survives to the motor pool.  That number comes from 1/sqrt(1+(w*tau)^2), a
small-signal formula, and spike thresholds are not small-signal.  This measures
the impulse response directly instead.

Inject current into the haltere afferents for one short bin, then step on with
no drive, logging wing motor spikes per bin.  The width of what comes back is
the model's actual temporal resolution.  A wingbeat is 4.59 ms; if the response
is tens of milliseconds wide, phase within a beat is unrecoverable no matter how
the afferents are driven.

Also runs a sustained-drive positive control, because "no response" and "no
*brief* response" are different findings and the pool is known to need sustained
drive to fire at all.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
WINGBEAT_MS = 1000.0 / 218.0


def run(*, dataset="malecns_v1", current=14.0, pulse_ms=1.0, follow_ms=60.0,
        bin_ms=0.5, sustain_ms=500.0,
        out=ROOT / "outputs/haltere_impulse.json") -> dict:
    from connectome_sim.native import NativeBrain
    from connectome_sim.physiology.common import annotations

    from experiments.haltere_axis_pairs import _readouts, _reset

    brain = NativeBrain(str(ROOT / "outputs/connectome_sim" / dataset / "graph.npz"))
    ann = annotations(brain.ids)
    groups = _readouts(ann)
    motor = np.concatenate(list(groups.values()))
    halteres = np.flatnonzero((ann.subclass == "haltere").to_numpy()).astype(np.int32)
    dark = np.zeros(len(brain.retina), dtype=np.float32)

    # Positive control first: does the pool respond to this current at all when
    # the drive is sustained?  Without this a flat impulse response is
    # uninterpretable.
    _reset(brain)
    counts, _ = brain.step(dark, sustain_ms, stimulation=(halteres, current))
    sustained = int(counts[motor].sum())

    # Impulse: drive for one bin, then follow with no drive.
    _reset(brain)
    trace = []
    n_pulse = max(1, int(round(pulse_ms / bin_ms)))
    n_follow = int(round(follow_ms / bin_ms))
    for i in range(n_pulse + n_follow):
        stim = (halteres, current) if i < n_pulse else None
        counts, _ = brain.step(dark, bin_ms, stimulation=stim)
        trace.append(int(counts[motor].sum()))

    # Baseline: identical protocol with no pulse, so spontaneous activity is not
    # read as a response.
    _reset(brain)
    base = []
    for _ in range(n_pulse + n_follow):
        counts, _ = brain.step(dark, bin_ms, None)
        base.append(int(counts[motor].sum()))

    t = np.arange(len(trace)) * bin_ms
    resp = np.asarray(trace, float) - np.asarray(base, float)
    total = resp.sum()
    peak = int(np.argmax(resp)) if total else 0
    width = _fwhm(t, resp) if total > 0 else None
    return _report(locals())


def _fwhm(t, y):
    """Full width at half maximum, linearly interpolated, in ms."""
    if y.max() <= 0:
        return None
    half = y.max() / 2
    above = np.flatnonzero(y >= half)
    if not len(above):
        return None
    return float(t[above[-1]] - t[above[0]] + (t[1] - t[0]))


def _report(ns) -> dict:
    t, resp = ns["t"], ns["resp"]
    total, width = ns["total"], ns["width"]
    report = {
        "dataset": ns["dataset"],
        "current_mV": ns["current"],
        "pulse_ms": ns["pulse_ms"],
        "bin_ms": ns["bin_ms"],
        "wingbeat_ms": round(WINGBEAT_MS, 3),
        "sustained_control_spikes": ns["sustained"],
        "impulse_total_spikes": float(total),
        "impulse_peak_ms": float(t[ns["peak"]]) if total else None,
        "impulse_fwhm_ms": width,
        # The number that decides the phase question: a response wider than a
        # wingbeat cannot carry within-beat timing.
        "fwhm_in_wingbeats": round(width / WINGBEAT_MS, 2) if width else None,
        "trace_ms": t.tolist(),
        "trace_spikes": resp.tolist(),
    }
    out = Path(ns["out"])
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(report, indent=2) + "\n")
    return report


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--current", type=float, default=14.0)
    p.add_argument("--pulse-ms", type=float, default=1.0)
    p.add_argument("--follow-ms", type=float, default=60.0)
    p.add_argument("--bin-ms", type=float, default=0.5)
    p.add_argument("--out", default=str(ROOT / "outputs/haltere_impulse.json"))
    a = p.parse_args()
    r = run(current=a.current, pulse_ms=a.pulse_ms, follow_ms=a.follow_ms,
            bin_ms=a.bin_ms, out=a.out)
    print(json.dumps({k: v for k, v in r.items() if not k.startswith("trace")}, indent=2))
