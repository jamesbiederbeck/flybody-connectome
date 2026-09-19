"""Re-add the wing fluid and inertial geoms that FlyGym's FlyBody import drops.

Upstream flybody's `fruitfly.xml` gives each wing four geoms beyond the visual
meshes: a collision ellipsoid, a membrane collision ellipsoid, a zero-mass
`*_fluid` ellipsoid and a small `*_inertial` box.  FlyGym's `FlyBody` keeps only
`{l,r}_wing_{brown,membrane}`, so the wing's interaction volume with the fluid
medium is missing.

That matters because MuJoCo derives fluid forces from geometry.  Neither model
enables the per-geom ellipsoid fluid model, so lift and drag come from the
inertia-box model applied to whatever geometry each wing body actually has.
Dropping the fluid ellipsoid therefore changes the aerodynamics rather than just
the rendering.  (Both models also carry the same *numbers* for the global medium,
0.00128 and 0.000185 -- but those are cm-unit values and FlyGym's model is in mm,
so it is 1000x too dense as shipped.  `fly.body` corrects it; see its docstring.)

Numbers below are copied verbatim from `fruitfly.xml:388-389` (and the mirrored
right-wing lines) with the `wing-fluid` / `wing-inertial` defaults at `:71-76`
folded in.  Upstream authors in cm; FlyGym works in mm, so lengths scale x10 --
the same convention as `flygym/flybody/parse_flybody.py`.

Whether flight additionally wants `fluidshape="ellipsoid"` set on these geoms is
open.  Upstream does not set it, so the default here does not either;
`ellipsoid_fluid=True` turns it on for experiments.  Measured, it moves net lift
from -0.023 to +0.075 body weights -- from zero to zero -- so it settles nothing
while the stroke pattern is a bare sine.  See README, "Does it fly?".
"""

from __future__ import annotations

import numpy as np

CM_TO_MM = 10.0

# name -> (half-size, position, quaternion) in the wing body's frame, centimetres.
_WING_GEOMS = {
    "l_wing_fluid": dict(
        kind="ellipsoid", mass=0.0, group=3,
        size=(0.0005, 0.0551, 0.114),
        pos=(0.0263, -0.148, -0.0289),
        quat=(-0.685, -0.634, 0.265, -0.243),
    ),
    "l_wing_inertial": dict(
        kind="box", mass=8e-06, group=3,
        size=(0.0005, 0.0551, 0.114),
        pos=(0.0263, -0.148, -0.0289),
        quat=(-0.685, -0.634, 0.265, -0.243),
    ),
    "r_wing_fluid": dict(
        kind="ellipsoid", mass=0.0, group=3,
        size=(0.0005, 0.0551, 0.114),
        pos=(-0.0263, 0.148, 0.0289),
        quat=(0.243, 0.265, 0.634, -0.685),
    ),
    "r_wing_inertial": dict(
        kind="box", mass=8e-06, group=3,
        size=(0.0005, 0.0551, 0.114),
        pos=(-0.0263, 0.148, 0.0289),
        quat=(0.243, 0.265, 0.634, -0.685),
    ),
}

# Wing body names differ between the two models; FlyGym renames on import.
_WING_BODY = {"l": "l_wing", "r": "r_wing"}


def add_wing_fluid_geoms(fly, *, ellipsoid_fluid: bool = False) -> list[str]:
    """Attach the missing wing geoms to an already-constructed FlyGym `FlyBody`.

    Call after `add_joints`/`add_actuators` and before the world compiles the
    model.  Returns the names of the geoms that were added.

    Args:
        fly: A `flygym.compose.fly.FlyBody` instance.
        ellipsoid_fluid: Enable MuJoCo's per-geom ellipsoid fluid model on the
            `*_fluid` geoms.  Upstream flybody leaves this off and relies on the
            global medium; turning it on is an experiment, not a fix.

    Returns:
        The names of the geoms added, in insertion order.
    """
    import mujoco as mj

    kinds = {"ellipsoid": mj.mjtGeom.mjGEOM_ELLIPSOID, "box": mj.mjtGeom.mjGEOM_BOX}
    spec = fly.mjcf_root
    added: list[str] = []
    for name, geom_spec in _WING_GEOMS.items():
        body = spec.body(_WING_BODY[name[0]])
        if body is None:
            raise ValueError(
                f"Could not find wing body {_WING_BODY[name[0]]!r} on {fly.name!r}. "
                "FlyGym may have renamed it; check fly.mjcf_root.bodies."
            )
        geom = body.add_geom()
        geom.name = name
        geom.type = kinds[geom_spec["kind"]]
        geom.size = np.asarray(geom_spec["size"], dtype=float) * CM_TO_MM
        geom.pos = np.asarray(geom_spec["pos"], dtype=float) * CM_TO_MM
        geom.quat = np.asarray(geom_spec["quat"], dtype=float)
        geom.mass = geom_spec["mass"]
        geom.group = geom_spec["group"]
        geom.rgba = np.array([0.0, 0.0, 0.0, 0.0])
        # Invisible to the eye cameras and inert in contact: these exist only to
        # give the wing a fluid-interaction volume.
        geom.contype = 0
        geom.conaffinity = 0
        if ellipsoid_fluid and geom_spec["kind"] == "ellipsoid":
            geom.fluid_ellipsoid = 1.0
        added.append(name)
    return added
