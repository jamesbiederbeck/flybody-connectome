"""Decode spike counts into continuous wing actuator targets.

Nothing in this project family did this before.  `connectome_sim.engine`'s
`NeuralControls` collapses the whole graph to two scalars and a boolean
(turn/forward/attack), and `flappy-haltere` decodes a single flap bool.  Here the
output has to be shaped like the motor periphery: a per-actuator vector.

The filtering matches `NeuralControls.decode` -- a per-readout exponential
moving average of firing rate with tau = 0.1 s -- but vectorised over readouts
instead of reduced to scalars, so each steering muscle keeps its own trace.

**Which cells to decode from is not a free choice.**  Measurement on MaleCNS v1.0
(see README, "What actually connects") shows retinal input reaches the descending
neurons -- DNp20 and DNpe017 fire -- but *no* VNC motor neuron fires from vision:
all 708 are silent, wing muscles included.  The VNC motor pool is only reachable
by stimulating haltere afferents directly.  So:

* `source="descending"` (the default) decodes DNp20 right-minus-left for steering
  and DNpe017 for drive.  This is the pathway that actually carries visual
  information in this dataset.
* `source="motor"` decodes the b1/b2/hg1 and DLM motor neurons.  Anatomically
  this is the right place to read a wing command, and it is what a complete
  connectome would allow -- but in this one it produces silence unless haltere
  current is being injected.  Kept because it is the target to grow into, and
  because the haltere-driven case is exactly the joystick this project is after.

**Every gain in this module is an engineering choice.**  The connectome tells us
which cells are b1/b2/hg1 motor neurons and which are DLMs; it does not tell us
how many radians of stroke deviation one spike is worth.  These numbers were
picked to put typical firing rates in the middle of each actuator's range, and
they are the first thing to question if the fly behaves oddly.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import numpy as np

# Matches NeuralControls.decode's smoothing (connectome_sim/engine.py).
TAU_SECONDS = 0.1

# Wing actuator order as body.WING_ACTUATORS declares it.
_ANGLES = ("yaw", "roll", "pitch")


@dataclass
class FlightControls:
    """Rate -> wing actuator decoder for one fly.

    Args:
        power_readouts: DLM readout dicts from `circuit.power_muscle_readouts`.
        steering_readouts: b1/b2/hg1 dicts from `circuit.steering_muscle_readouts`.
        base_freq_hz: Wingbeat frequency at zero DLM drive.
        freq_span_hz: Half-width of the commanded frequency range.  The vendored
            WPG only generates base_freq +/- 5%, so anything wider is clipped by
            it anyway.
        freq_gain: Hz per Hz of mean DLM firing rate.
        steer_gain: Actuator units per Hz of left-minus-right rate difference.
        steer_limit: Clip on the per-angle steering deviation.
    """

    power_readouts: list[dict]
    steering_readouts: list[dict]
    source: str = "motor"
    base_freq_hz: float = 218.0
    freq_span_hz: float = 10.0
    freq_gain: float = 0.5
    steer_gain: float = 0.02
    steer_limit: float = 0.6

    _power_idx: np.ndarray = field(init=False)
    _steer_idx: np.ndarray = field(init=False)
    _steer_side: np.ndarray = field(init=False)
    _steer_angle: np.ndarray = field(init=False)
    _power_rate: np.ndarray = field(init=False)
    _steer_rate: np.ndarray = field(init=False)

    @classmethod
    def from_descending(cls, brain, **kw) -> "FlightControls":
        """Build the controller on the pathway vision actually reaches.

        DNp20 supplies the left/right steering difference; DNpe017 supplies the
        scalar drive that sets wingbeat frequency.
        """
        from fly import circuit

        readouts = circuit.descending_readouts(brain)
        steering = [r for r in readouts if r["type"] == circuit.DESCENDING_STEERING_TYPE]
        power = [r for r in readouts if r["type"] == circuit.DESCENDING_DRIVE_TYPE]
        if not steering or not power:
            raise ValueError(
                "Graph lacks DNp20 and/or DNpe017; cannot build a descending controller."
            )
        # All DNp20 cells steer, so they share the single 'yaw' axis rather than
        # being split across b1/b2/hg1's three.
        for r in steering:
            r = r.setdefault("type", circuit.DESCENDING_STEERING_TYPE)
        return cls(power, steering, source="descending", **kw)

    def __post_init__(self):
        if self.source not in ("motor", "descending"):
            raise ValueError(f"Unknown readout source: {self.source!r}")
        if not self.power_readouts:
            raise ValueError("No power-muscle readouts supplied")
        if not self.steering_readouts:
            raise ValueError("No steering-muscle readouts supplied")
        self._power_idx = np.array([r["index"] for r in self.power_readouts], dtype=np.int64)
        usable = [r for r in self.steering_readouts if r.get("side") in ("L", "R")]
        if not usable:
            raise ValueError("No steering readouts with a resolved L/R side")
        self._steer_idx = np.array([r["index"] for r in usable], dtype=np.int64)
        self._steer_side = np.array([1.0 if r["side"] == "L" else -1.0 for r in usable])
        # b1 -> yaw, b2 -> roll, hg1 -> pitch.  The assignment of a steering
        # muscle to a wing rotation axis is ours, not measured: b1/b2/hg1 all
        # act on the wing hinge and their real effects are coupled.
        # b1 -> yaw, b2 -> roll, hg1 -> pitch. Descending steering has no such
        # decomposition, so every DNp20 cell drives the yaw axis.
        angle_of = {"b1 MN": 0, "b2 MN": 1, "hg1 MN": 2}
        self._steer_angle = np.array(
            [angle_of.get(r["type"], 0) for r in usable], dtype=np.int64
        )
        self._power_rate = np.zeros(len(self._power_idx))
        self._steer_rate = np.zeros(len(self._steer_idx))

    @property
    def n_steering(self) -> int:
        return int(len(self._steer_idx))

    def reset(self) -> None:
        self._power_rate[:] = 0.0
        self._steer_rate[:] = 0.0

    def decode(self, counts, seconds: float) -> dict:
        """Update the EMA traces and return the commanded wing action.

        Args:
            counts: Per-neuron spike counts for this step, as `Brain.step`
                returns them.
            seconds: Duration of the step in seconds.

        Returns:
            A dict with `wingbeat_hz` (scalar), `wing_offsets` (6-vector, in the
            order `body.WING_ACTUATORS`), and the per-side per-angle rates
            behind them, for telemetry.
        """
        if seconds <= 0:
            raise ValueError("Step duration must be positive")
        counts = np.asarray(counts)
        alpha = 1.0 - np.exp(-seconds / TAU_SECONDS)

        self._power_rate += alpha * (counts[self._power_idx] / seconds - self._power_rate)
        self._steer_rate += alpha * (counts[self._steer_idx] / seconds - self._steer_rate)

        freq = self.base_freq_hz + self.freq_gain * float(self._power_rate.mean())
        freq = float(np.clip(freq,
                             self.base_freq_hz - self.freq_span_hz,
                             self.base_freq_hz + self.freq_span_hz))

        # Per (angle, side) mean rate, then a left-minus-right difference.
        left = np.zeros(3)
        right = np.zeros(3)
        for angle in range(3):
            m = self._steer_angle == angle
            if not m.any():
                continue
            l = m & (self._steer_side > 0)
            r = m & (self._steer_side < 0)
            left[angle] = self._steer_rate[l].mean() if l.any() else 0.0
            right[angle] = self._steer_rate[r].mean() if r.any() else 0.0

        deviation = np.clip(self.steer_gain * (left - right),
                            -self.steer_limit, self.steer_limit)
        # Antisymmetric: a left-biased command deviates the left wing one way
        # and the right wing the other, which is what turns the fly.
        offsets = np.concatenate([deviation, -deviation])
        return {
            "wingbeat_hz": freq,
            "wing_offsets": offsets,
            "left_rate_hz": dict(zip(_ANGLES, left.round(4))),
            "right_rate_hz": dict(zip(_ANGLES, right.round(4))),
            "power_rate_hz": float(self._power_rate.mean()),
        }
