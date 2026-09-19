"""Hex-lattice registration and the pale/yellow channel collapse."""
import numpy as np
import pytest

from fly import retina_map as rm


def _hex_disc(radius: int) -> np.ndarray:
    """Axial hex coordinates filling a disc, as an optic lobe's columns do."""
    out = []
    for q in range(-radius, radius + 1):
        for r in range(-radius, radius + 1):
            # Hex distance in the 120-degree convention prepare.py uses.
            if abs(q) <= radius and abs(r) <= radius and abs(q - r) <= radius:
                out.append((q, r))
    return np.array(out, dtype=float)


def test_hex_to_cartesian_preserves_lattice_spacing():
    """The six lattice neighbours of the origin are all one unit away.

    prepare.py embeds axial coordinates as (h1 - h2/2, sqrt(3)/2 * h2), which
    puts the two basis vectors 120 degrees apart.  The unit-distance neighbours
    are therefore +/-(1,0), +/-(0,1) and +/-(1,1) -- not the (1,-1)/(-1,1) pair
    of the 60-degree axial convention.
    """
    neighbours = np.array([[1, 0], [0, 1], [1, 1], [-1, 0], [0, -1], [-1, -1]], dtype=float)
    xy = rm.hex_to_cartesian(neighbours)
    assert np.allclose(np.linalg.norm(xy, axis=1), 1.0)
    # (1,0) and (0,1) are neighbours of the origin but two steps from each other.
    two_step = rm.hex_to_cartesian(np.array([[1, 0], [0, 1]], dtype=float))
    assert np.linalg.norm(two_step[0] - two_step[1]) == pytest.approx(np.sqrt(3))


def test_ommatidia_centroids_shape_and_positions():
    id_map = np.zeros((10, 10), dtype=int)
    id_map[0:2, 0:2] = 1
    id_map[8:10, 8:10] = 2
    c = rm.ommatidia_centroids(id_map)
    assert c.shape == (2, 2)
    assert np.allclose(c[0], [0.5, 0.5])
    assert np.allclose(c[1], [8.5, 8.5])


def test_ommatidia_centroids_rejects_gaps():
    id_map = np.zeros((4, 4), dtype=int)
    id_map[0, 0] = 1
    id_map[1, 1] = 3          # ommatidium 2 has no pixels
    with pytest.raises(ValueError, match="no pixels"):
        rm.ommatidia_centroids(id_map)


def test_registration_recovers_a_known_transform():
    """A rotated, scaled, shifted copy of a lattice should register onto it."""
    target = rm.hex_to_cartesian(_hex_disc(6))
    theta = np.pi / 3.0
    rot = np.array([[np.cos(theta), -np.sin(theta)], [np.sin(theta), np.cos(theta)]])
    source = target @ rot.T * 3.7 + np.array([120.0, -45.0])

    reg = rm.register(source, target)
    assert reg.unmatched == 0
    assert reg.residual_rms < 1e-6
    # Every column should land on a distinct ommatidium.
    assert len(set(reg.assignment.tolist())) == len(target)


def test_registration_handles_a_partial_covering():
    """Fewer columns than ommatidia is the real case (~556 vs 721 per eye)."""
    target = rm.hex_to_cartesian(_hex_disc(8))
    subset = target[::2]
    reg = rm.register(subset, target)
    assert reg.n_columns == len(subset)
    assert reg.n_ommatidia == len(target)
    assert reg.unmatched == 0
    assert reg.residual_rms < 1e-6


def test_registration_reports_rather_than_raises_on_a_bad_fit():
    rng = np.random.default_rng(0)
    reg = rm.register(rng.normal(size=(50, 2)), rm.hex_to_cartesian(_hex_disc(6)))
    assert reg.residual_rms > 0
    m = reg.as_manifest()
    assert set(m) >= {"columns", "ommatidia", "matched", "unmatched", "residual_rms"}
    assert m["matched"] + m["unmatched"] == m["columns"]


def test_achromatic_sums_the_two_channels():
    """Exactly one of the pale/yellow channels is populated per ommatidium."""
    r = np.zeros((2, 5, 2))
    r[0, :3, 0] = 0.4          # yellow-type
    r[0, 3:, 1] = 0.7          # pale-type
    out = rm.achromatic(r)
    assert out.shape == (2, 5)
    assert np.allclose(out[0], [0.4, 0.4, 0.4, 0.7, 0.7])
    # Taking [..., 0] would zero every pale ommatidium; summing does not.
    assert not np.allclose(out[0], r[0, :, 0])


def test_achromatic_rejects_a_wrong_channel_axis():
    with pytest.raises(ValueError, match="channel axis"):
        rm.achromatic(np.zeros((2, 5, 3)))
