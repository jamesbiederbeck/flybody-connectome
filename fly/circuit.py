"""Which cells drive the wings, and which take proprioceptive input.

Every population here is selected at runtime from the MaleCNS annotations via
`connectome_sim.physiology.common.annotations`, the same approach
`flappy-haltere/flappy/circuit.py` uses.  Nothing is hardcoded into the graph, so
a different dataset or a corrected annotation changes the selection without a
rebuild.

The split follows the real fly's flight motor periphery:

* **Power muscles** (DLM) set how hard the thorax oscillates.  *Drosophila* is an
  asynchronous flier -- these motor neurons fire far slower than the wingbeat and
  do not pattern individual strokes -- so their *rate* maps to wingbeat
  frequency, not to wing position.  See `vendor/pattern_generators.py`.
* **Steering muscles** (b1, b2, hg1) are synchronous, fire phase-locked to the
  stroke, and deform its shape.  Their left/right rate difference is what steers.

That the connectome contains these cells is measured.  That we map their firing
rates onto MuJoCo actuator targets with particular gains is an engineering
choice, and `controls.py` says so where the gains live.
"""

from __future__ import annotations

import numpy as np

from connectome_sim.physiology.common import annotations

# Power muscle motor neurons: the indirect flight muscles that drive the thorax.
DLM_TYPES = ["DLMn a, b", "DLMn c-f"]

# Direct (steering) flight muscle motor neurons, per fly_regions.py's mapping.
STEERING_TYPES = ["b1 MN", "b2 MN", "hg1 MN"]

# Descending neurons that visual input actually reaches in this graph. DNp20 is
# bilateral, so its right-minus-left difference is a steering signal; DNpe017's
# summed rate is a scalar drive. These are the same cells DOOMFLY decodes, and
# measurement (see README, "What actually connects") shows they are the only
# visually-driven output available -- the VNC motor neurons are not reachable
# from the eyes in MaleCNS v1.0.
DESCENDING_STEERING_TYPE = "DNp20"
DESCENDING_DRIVE_TYPE = "DNpe017"


def descending_readouts(brain, types=(DESCENDING_STEERING_TYPE, DESCENDING_DRIVE_TYPE)) -> list[dict]:
    """Visually-driven descending neurons, as readout dicts.

    Unlike the wing motor neurons, these do fire in response to retinal input,
    which is why the default flight controller decodes from them.
    """
    a = annotations(brain.ids)
    idx = np.flatnonzero(a.type.isin(list(types)).to_numpy())
    if not len(idx):
        raise ValueError(f"No descending neurons of types {tuple(types)} in this graph")
    out = []
    for i in idx:
        side = str(a.somaSide.iloc[i])
        out.append({
            "index": int(i),
            "id": str(brain.ids[i]),
            "type": str(a.type.iloc[i]),
            "side": side if side in ("L", "R") else "?",
        })
    return out


def power_muscle_readouts(brain) -> list[dict]:
    """DLM motor neurons, as `NeuralControls`-style readout dicts."""
    a = annotations(brain.ids)
    idx = np.flatnonzero(a.type.isin(DLM_TYPES).to_numpy())
    if not len(idx):
        raise ValueError("No DLM motor neurons found in this graph")
    return [
        {
            "index": int(i),
            "id": str(brain.ids[i]),
            "type": "DLMn",
            "connectome_type": str(a.type.iloc[i]),
            "side": str(a.somaSide.iloc[i]),
        }
        for i in idx
    ]


def steering_muscle_readouts(brain) -> list[dict]:
    """b1/b2/hg1 motor neurons, tagged with the side they steer."""
    a = annotations(brain.ids)
    idx = np.flatnonzero(a.type.isin(STEERING_TYPES).to_numpy())
    if not len(idx):
        raise ValueError("No b1/b2/hg1 steering motor neurons found in this graph")
    out = []
    for i in idx:
        side = str(a.somaSide.iloc[i])
        if side not in ("L", "R"):
            # Recorded but unusable for a left-minus-right decode; keep it
            # visible rather than dropping it silently.
            side = "?"
        out.append(
            {
                "index": int(i),
                "id": str(brain.ids[i]),
                "type": str(a.type.iloc[i]),
                "side": side,
            }
        )
    return out


def haltere_afferents(brain) -> np.ndarray:
    """Graph indices of the haltere mechanosensory afferents.

    The halteres are the fly's real flight gyroscope, which is why they are the
    natural place to inject an angular-velocity signal -- see
    `proprioceptive_stimulation`.
    """
    a = annotations(brain.ids)
    idx = np.flatnonzero((a.subclass == "haltere").to_numpy())
    if not len(idx):
        raise ValueError("No haltere afferents found in this graph")
    return idx.astype(np.int32)


def proprioceptive_stimulation(indices: np.ndarray,
                               angular_velocity,
                               *,
                               gain: float = 1.0,
                               max_rate: float = 20.0):
    """Turn a body angular-velocity vector into a haltere current injection.

    **This is an engineered joystick, not a model of campaniform transduction.**
    Real haltere afferents encode Coriolis forces on a beating haltere with
    spike timing locked to the stroke; here we inject a current proportional to
    the magnitude of the body's angular velocity, host-side, before the audited
    kernel runs.  `flappy-haltere/AGENTS.md` makes the same caveat about its own
    haltere drive and it applies unchanged.

    The signature takes a plain 3-vector rather than anything MuJoCo-specific,
    so the same drive can later be fed from a phone IMU or an airframe.

    Args:
        indices: Graph indices from `haltere_afferents`.
        angular_velocity: Body angular velocity, any length-3 sequence, rad/s.
        gain: Current per rad/s.
        max_rate: Clip magnitude before scaling, so a physics blow-up cannot
            inject unbounded current.

    Returns:
        A `(indices, amplitude)` pair for `Brain.step(stimulation=...)`, or
        `None` when there is nothing to inject.  Note only `NativeBrain`,
        `GPUBrain` and `MemoryBrain` accept `stimulation`; the pure-numba
        `Brain` does not.
    """
    w = np.asarray(angular_velocity, dtype=float).reshape(-1)
    if w.size != 3:
        raise ValueError(f"Expected a 3-vector angular velocity, got shape {w.shape}")
    if not np.all(np.isfinite(w)):
        raise ValueError("Angular velocity must be finite")
    magnitude = min(float(np.linalg.norm(w)), max_rate)
    current = gain * magnitude
    if current <= 0:
        return None
    return (indices, current)
