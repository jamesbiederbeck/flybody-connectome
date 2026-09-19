"""Cell-identity selection, against a synthetic brain (no real graph needed)."""
import numpy as np
import pytest

from fly import circuit


@pytest.fixture(autouse=True)
def _patch_annotations(monkeypatch, fake_annotations):
    _, frame = fake_annotations
    monkeypatch.setattr(circuit, "annotations", lambda ids: frame.loc[list(ids)])


def test_power_muscles_are_the_dlms(fake_annotations):
    brain, _ = fake_annotations
    got = circuit.power_muscle_readouts(brain)
    assert [r["connectome_type"] for r in got] == ["DLMn a, b", "DLMn c-f"]
    assert {r["type"] for r in got} == {"DLMn"}


def test_steering_muscles_are_b1_b2_hg1(fake_annotations):
    brain, _ = fake_annotations
    got = circuit.steering_muscle_readouts(brain)
    assert len(got) == 6
    assert {r["type"] for r in got} == {"b1 MN", "b2 MN", "hg1 MN"}
    assert sorted(r["side"] for r in got) == ["L", "L", "L", "R", "R", "R"]


def test_halteres_selected_by_subclass(fake_annotations):
    brain, _ = fake_annotations
    idx = circuit.haltere_afferents(brain)
    assert idx.dtype == np.int32
    assert sorted(brain.ids[idx]) == [9, 10]


def test_missing_population_raises(fake_annotations, monkeypatch):
    brain, frame = fake_annotations
    stripped = frame[frame.subclass != "haltere"]
    monkeypatch.setattr(circuit, "annotations", lambda ids: stripped)
    with pytest.raises(ValueError, match="haltere"):
        circuit.haltere_afferents(brain)


def test_proprioceptive_stimulation_shape_and_bounds():
    idx = np.array([1, 2], dtype=np.int32)
    assert circuit.proprioceptive_stimulation(idx, [0, 0, 0]) is None
    indices, amp = circuit.proprioceptive_stimulation(idx, [3.0, 4.0, 0.0], gain=2.0)
    assert np.array_equal(indices, idx)
    assert amp == pytest.approx(10.0)          # |(3,4,0)| = 5, x gain 2


def test_proprioceptive_stimulation_clips_blowups():
    idx = np.array([0], dtype=np.int32)
    _, amp = circuit.proprioceptive_stimulation(idx, [1e9, 0, 0], gain=1.0, max_rate=20.0)
    assert amp == pytest.approx(20.0)


def test_proprioceptive_stimulation_rejects_bad_input():
    idx = np.array([0], dtype=np.int32)
    with pytest.raises(ValueError):
        circuit.proprioceptive_stimulation(idx, [1.0, 2.0])
    with pytest.raises(ValueError):
        circuit.proprioceptive_stimulation(idx, [np.nan, 0, 0])
