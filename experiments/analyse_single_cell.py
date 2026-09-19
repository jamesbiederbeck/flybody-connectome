"""Concentration analysis for the single-cell sweep.

Answers one question: within a haltere type, is potency spread across its cells
or carried by one or two?  Reported as the top cell's share of the type's summed
single-cell response, and as a Gini coefficient over the type's cells.

A high share means cluster-level stimulation averages a potent cell with silent
ones, and every cluster-level null in the log is suspect for that reason.
"""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def gini(x):
    x = np.sort(np.asarray(x, dtype=float))
    if x.sum() <= 0:
        return 0.0
    n = len(x)
    return float((2 * np.arange(1, n + 1) - n - 1) @ x / (n * x.sum()))


def main(path=ROOT / "outputs/haltere_single_cell.json", current="20.0"):
    r = json.load(open(path))
    cells = r["cells"]
    tot = np.array([c["by_current"][current]["total"] for c in cells], float)
    print(f"205 haltere afferents, single-cell drive at {current} mV, "
          f"{r['duration_ms']:.0f} ms\n")
    print(f"cells producing 0 motor spikes: {int((tot <= 0).sum())}/{len(tot)}")
    print(f"cells producing >100:           {int((tot > 100).sum())}")
    order = np.argsort(-tot)
    share = tot[order].cumsum() / max(tot.sum(), 1)
    for k in (1, 3, 5, 10, 20):
        if k <= len(tot):
            print(f"  top {k:2d} cells account for {share[k-1]:6.1%} of all single-cell response")
    print(f"\nGini across all 205 cells: {gini(tot):.3f}  (0 = uniform, 1 = one cell)")

    print(f"\n{'type':12s} {'n':>3s} {'sum':>7s} {'top cell':>9s} {'share':>7s} {'gini':>6s}  top body_id")
    by = {}
    for c, v in zip(cells, tot):
        by.setdefault(c["type"], []).append((v, c))
    for t, members in sorted(by.items(), key=lambda kv: -sum(m[0] for m in kv[1])):
        vals = np.array([m[0] for m in members])
        best = max(members, key=lambda m: m[0])
        s = vals.sum()
        print(f"{t:12s} {len(vals):3d} {s:7.0f} {best[0]:9.0f} "
              f"{(best[0]/s if s else 0):7.1%} {gini(vals):6.3f}  {best[1]['body_id']} "
              f"({best[1]['side']})")


if __name__ == "__main__":
    import sys
    main(current=sys.argv[1] if len(sys.argv) > 1 else "20.0")
