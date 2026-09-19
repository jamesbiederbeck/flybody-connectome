"""Register the connectome's ommatidial columns onto FlyGym's ommatidia lattice.

Both sides of this are real hex lattices, so the correspondence is a 2D
registration problem -- not an angular projection to be invented.

* The connectome side comes from `prepare.py`'s modal-column inference: for each
  R1-R6 cell, the optical-lobe column it contacts most strongly, as axial hex
  coordinates `(h1, h2)`.  That is a measurement over all released
  R1-R6 -> L1/L2/L3 contacts.
* The FlyGym side is NeuroMechFly v2's compound eye: 721 ommatidia per eye on a
  hex lattice, with the fisheye optics and acceptance-angle binning described in
  supplementary note 5 of the Nature Methods paper.

The two come from **different animals** -- MaleCNS v1.0 versus a female micro-CT
scan -- so this is a fitted alignment, not an identity.  `register` reports its
residual and how many columns went unmatched; those numbers belong in the
manifest and in any writeup.  If they are bad that is a finding about the two
datasets, not something to tune away.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

# Axial hex -> cartesian, the same embedding prepare.py uses.
_HEX_BASIS = np.array([[1.0, -0.5], [0.0, np.sqrt(3.0) / 2.0]])


def hex_to_cartesian(hexes: np.ndarray) -> np.ndarray:
    """Axial hex coordinates `(n, 2)` -> cartesian `(n, 2)`."""
    hexes = np.asarray(hexes, dtype=float)
    return np.column_stack([hexes[:, 0] - 0.5 * hexes[:, 1],
                            np.sqrt(3.0) / 2.0 * hexes[:, 1]])


def ommatidia_centroids(ommatidia_id_map: np.ndarray) -> np.ndarray:
    """Pixel centroid of each ommatidium, `(n_ommatidia, 2)` as (x, y).

    `ommatidia_id_map` is FlyGym's `(nrows, ncols)` integer map where 0 is
    background and ommatidia are numbered from 1.
    """
    id_map = np.asarray(ommatidia_id_map)
    n = int(id_map.max())
    ys, xs = np.nonzero(id_map)
    ids = id_map[ys, xs] - 1
    counts = np.bincount(ids, minlength=n).astype(float)
    if np.any(counts == 0):
        missing = int((counts == 0).sum())
        raise ValueError(f"{missing} ommatidia have no pixels in the id map.")
    cx = np.bincount(ids, weights=xs.astype(float), minlength=n) / counts
    cy = np.bincount(ids, weights=ys.astype(float), minlength=n) / counts
    return np.column_stack([cx, cy])


def _normalize(points: np.ndarray) -> tuple[np.ndarray, np.ndarray, float]:
    """Center on the centroid and scale to unit RMS radius."""
    centre = points.mean(axis=0)
    centred = points - centre
    scale = float(np.sqrt((centred ** 2).sum(axis=1).mean()))
    if scale == 0:
        raise ValueError("Degenerate point set: all points coincide.")
    return centred / scale, centre, scale


def _rotation(theta: float) -> np.ndarray:
    c, s = np.cos(theta), np.sin(theta)
    return np.array([[c, -s], [s, c]])


@dataclass
class Registration:
    """The fitted column -> ommatidium correspondence for one eye."""

    assignment: np.ndarray        # (n_columns,) index into ommatidia, -1 if unmatched
    residual_rms: float           # RMS nearest-neighbour distance, normalized units
    residual_median: float
    unmatched: int
    theta: float                  # fitted rotation, radians
    flipped: bool                 # whether a chirality flip was needed
    n_columns: int
    n_ommatidia: int

    def as_manifest(self) -> dict:
        """The numbers that belong in the graph manifest."""
        return {
            "columns": self.n_columns,
            "ommatidia": self.n_ommatidia,
            "matched": int(self.n_columns - self.unmatched),
            "unmatched": int(self.unmatched),
            "residual_rms": round(float(self.residual_rms), 6),
            "residual_median": round(float(self.residual_median), 6),
            "rotation_deg": round(float(np.degrees(self.theta)), 3),
            "chirality_flipped": bool(self.flipped),
        }


def register(column_xy: np.ndarray,
             ommatidia_xy: np.ndarray,
             *,
             max_distance: float = 0.5,
             refine_iterations: int = 20) -> Registration:
    """Fit a similarity transform from connectome columns onto ommatidia.

    A hex lattice has 6-fold symmetry, so the rotation is only determined up to
    60 degrees by the lattice itself; the search below tries all six, with and
    without a chirality flip, and keeps whichever minimises nearest-neighbour
    distance.  It then runs a few Procrustes/ICP refinement rounds.

    Distances are in normalized units where each point set has unit RMS radius,
    so `max_distance` is a fraction of the eye's angular radius, not pixels.

    Args:
        column_xy: `(n_columns, 2)` cartesian hex coordinates for one eye.
        ommatidia_xy: `(n_ommatidia, 2)` ommatidium centroids for one eye.
        max_distance: Columns whose nearest ommatidium is further than this are
            left unmatched rather than forced onto a distant neighbour.
        refine_iterations: ICP rounds after the coarse symmetry search.

    Returns:
        A `Registration`.  Never raises on a poor fit -- inspect the residual.
    """
    src, _, _ = _normalize(np.asarray(column_xy, dtype=float))
    dst, _, _ = _normalize(np.asarray(ommatidia_xy, dtype=float))

    best = None
    for flip in (False, True):
        candidate = src * np.array([-1.0, 1.0]) if flip else src
        for k in range(6):
            theta = k * np.pi / 3.0
            moved = candidate @ _rotation(theta).T
            cost = _nearest(moved, dst)[1].mean()
            if best is None or cost < best[0]:
                best = (cost, theta, flip)

    _, theta, flipped = best
    current = (src * np.array([-1.0, 1.0]) if flipped else src) @ _rotation(theta).T

    # ICP: re-fit the similarity transform to the current correspondence.
    for _ in range(refine_iterations):
        idx, dist = _nearest(current, dst)
        keep = dist <= max_distance
        if keep.sum() < 3:
            break
        a, b = current[keep], dst[idx[keep]]
        rot, scale = _procrustes(a, b)
        updated = (current - a.mean(0)) @ rot.T * scale + b.mean(0)
        if np.allclose(updated, current, atol=1e-9):
            current = updated
            break
        current = updated

    idx, dist = _nearest(current, dst)
    matched = dist <= max_distance
    assignment = np.where(matched, idx, -1).astype(np.int32)
    resid = dist[matched] if matched.any() else dist
    return Registration(
        assignment=assignment,
        residual_rms=float(np.sqrt((resid ** 2).mean())),
        residual_median=float(np.median(resid)),
        unmatched=int((~matched).sum()),
        theta=float(theta),
        flipped=bool(flipped),
        n_columns=int(len(src)),
        n_ommatidia=int(len(dst)),
    )


def _nearest(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """For each row of `a`, the index of and distance to the nearest row of `b`."""
    d = np.linalg.norm(a[:, None, :] - b[None, :, :], axis=2)
    idx = np.argmin(d, axis=1)
    return idx, d[np.arange(len(a)), idx]


def _procrustes(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, float]:
    """Best rotation+scale taking centred `a` onto centred `b`."""
    ac, bc = a - a.mean(0), b - b.mean(0)
    u, s, vt = np.linalg.svd(ac.T @ bc)
    rot = (u @ vt).T
    if np.linalg.det(rot) < 0:                 # keep it a rotation, not a reflection
        vt[-1] *= -1
        s = s.copy(); s[-1] *= -1
        rot = (u @ vt).T
    denom = (ac ** 2).sum()
    scale = float(s.sum() / denom) if denom > 0 else 1.0
    return rot, scale


def achromatic(readouts: np.ndarray) -> np.ndarray:
    """Collapse FlyGym's `(..., n_ommatidia, 2)` readout to one value each.

    The last axis holds the yellow- and pale-type channels, and FlyGym populates
    exactly one per ommatidium (the other reads zero), per its `pale_type_mask`.
    Summing therefore recovers the single achromatic value each ommatidium
    reports -- which is what the R1-R6 pathway wants -- without silently
    discarding every pale ommatidium the way `[..., 0]` would.

    The discarded distinction is the R7/R8 spectral subtype; it is what could
    drive the connectome's separate R8 colour inputs later.
    """
    readouts = np.asarray(readouts)
    if readouts.shape[-1] != 2:
        raise ValueError(f"Expected a trailing channel axis of 2, got {readouts.shape}")
    return readouts.sum(axis=-1)
