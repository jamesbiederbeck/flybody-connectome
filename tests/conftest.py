"""Shared fixtures.

There is deliberately a conftest here, unlike the other repos in this family:
`androsophila/tests/test_flappy.py` imported `doom.game` at module scope and
broke when that harness moved out, so tests here import only what they need and
skip cleanly when an optional heavy dependency is absent.
"""
import numpy as np
import pytest


class FakeBrain:
    """Minimal stand-in for a Brain: just the bodyId array the selectors use."""

    def __init__(self, ids):
        self.ids = np.asarray(ids, dtype=np.int64)
        self.n = len(self.ids)


@pytest.fixture
def fake_annotations():
    """Build a (FakeBrain, annotations DataFrame) pair with known cell types.

    Cell-identity selection is pure annotation lookup, so it is tested against a
    handful of synthetic cells rather than the real 166,700-neuron graph.
    """
    pd = pytest.importorskip("pandas")

    rows = [
        (1, "DLMn a, b", "L", None),
        (2, "DLMn c-f", "R", None),
        (3, "b1 MN", "L", "wm"),
        (4, "b1 MN", "R", "wm"),
        (5, "b2 MN", "L", "wm"),
        (6, "b2 MN", "R", "wm"),
        (7, "hg1 MN", "L", "wm"),
        (8, "hg1 MN", "R", "wm"),
        (9, "HTR", "L", "haltere"),
        (10, "HTR", "R", "haltere"),
        (11, "Kenyon cell", "L", None),
    ]
    ids = [r[0] for r in rows]
    frame = pd.DataFrame(
        {
            "type": [r[1] for r in rows],
            "somaSide": [r[2] for r in rows],
            "rootSide": [r[2] for r in rows],
            "subclass": [r[3] for r in rows],
        },
        index=pd.Index(ids, name="bodyId"),
    )
    return FakeBrain(ids), frame
