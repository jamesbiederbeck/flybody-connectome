"""The rate -> actuator decoder."""
import numpy as np
import pytest

from fly.controls import TAU_SECONDS, FlightControls


def _readouts():
    power = [{"index": 0, "id": "1", "type": "DLMn", "connectome_type": "DLMn a, b", "side": "L"},
             {"index": 1, "id": "2", "type": "DLMn", "connectome_type": "DLMn c-f", "side": "R"}]
    steer = []
    for i, (t, s) in enumerate([("b1 MN", "L"), ("b1 MN", "R"),
                                ("b2 MN", "L"), ("b2 MN", "R"),
                                ("hg1 MN", "L"), ("hg1 MN", "R")], start=2):
        steer.append({"index": i, "id": str(i), "type": t, "side": s})
    return power, steer


def _controls(**kw):
    p, s = _readouts()
    return FlightControls(p, s, **kw)


def test_silence_gives_base_frequency_and_no_deflection():
    c = _controls()
    out = c.decode(np.zeros(8, dtype=np.int32), 0.033)
    assert out["wingbeat_hz"] == pytest.approx(c.base_freq_hz)
    assert np.allclose(out["wing_offsets"], 0.0)
    assert out["wing_offsets"].shape == (6,)


def test_left_bias_deflects_wings_antisymmetrically():
    c = _controls()
    counts = np.zeros(8, dtype=np.int32)
    counts[2] = 10                       # left b1 only
    out = c.decode(counts, 0.033)
    left, right = out["wing_offsets"][:3], out["wing_offsets"][3:]
    assert left[0] > 0 and right[0] < 0
    assert left[0] == pytest.approx(-right[0])


def test_right_bias_mirrors_left_bias():
    counts_l = np.zeros(8, dtype=np.int32); counts_l[2] = 10
    counts_r = np.zeros(8, dtype=np.int32); counts_r[3] = 10
    a = _controls().decode(counts_l, 0.033)["wing_offsets"]
    b = _controls().decode(counts_r, 0.033)["wing_offsets"]
    assert np.allclose(a, -b)


def test_deflection_is_clipped():
    c = _controls(steer_gain=1e6)
    counts = np.zeros(8, dtype=np.int32); counts[2] = 1000
    out = c.decode(counts, 0.033)
    assert np.abs(out["wing_offsets"]).max() <= c.steer_limit + 1e-9


def test_frequency_stays_inside_the_wpgs_range():
    c = _controls(freq_gain=1e6)
    counts = np.zeros(8, dtype=np.int32); counts[:2] = 5000
    out = c.decode(counts, 0.033)
    assert c.base_freq_hz - c.freq_span_hz <= out["wingbeat_hz"] <= c.base_freq_hz + c.freq_span_hz


def test_ema_matches_neuralcontrols_time_constant():
    """A constant input should approach its rate with tau = 0.1 s."""
    c = _controls()
    dt, spikes = 0.01, 1
    for _ in range(200):
        counts = np.zeros(8, dtype=np.int32); counts[:2] = spikes
        out = c.decode(counts, dt)
    assert out["power_rate_hz"] == pytest.approx(spikes / dt, rel=1e-3)

    c2 = _controls()
    counts = np.zeros(8, dtype=np.int32); counts[:2] = spikes
    first = c2.decode(counts, dt)["power_rate_hz"]
    alpha = 1.0 - np.exp(-dt / TAU_SECONDS)
    assert first == pytest.approx(alpha * spikes / dt)


def test_reset_clears_traces():
    c = _controls()
    counts = np.zeros(8, dtype=np.int32); counts[:2] = 50
    c.decode(counts, 0.033)
    c.reset()
    out = c.decode(np.zeros(8, dtype=np.int32), 0.033)
    assert out["power_rate_hz"] == pytest.approx(0.0)


def test_rejects_empty_or_sideless_populations():
    p, s = _readouts()
    with pytest.raises(ValueError, match="power-muscle"):
        FlightControls([], s)
    with pytest.raises(ValueError, match="resolved L/R"):
        FlightControls(p, [{"index": 2, "id": "2", "type": "b1 MN", "side": "?"}])


def test_rejects_nonpositive_duration():
    with pytest.raises(ValueError):
        _controls().decode(np.zeros(8, dtype=np.int32), 0.0)
