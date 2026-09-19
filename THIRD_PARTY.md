# Third-party sources

## FlyGym / NeuroMechFly v2 — Apache-2.0
<https://github.com/NeLy-EPFL/flygym>

Supplies the body model, the compound-eye cameras and the ommatidia sampling
pipeline (fisheye correction, hex-lattice binning, pale/yellow channels). Used as
an installed dependency; no files copied.

> Wang-Chen, S., et al. (2024). NeuroMechFly v2: simulating embodied sensorimotor
> control in adult *Drosophila*. *Nature Methods*.
> <https://doi.org/10.1038/s41592-024-02497-y>

The fisheye distortion coefficient (3.8) and zoom (2.72) this project relies on
are derived in supplementary note 5 of that paper.

## flybody — Apache-2.0
<https://github.com/TuragaLab/flybody>

The underlying biomechanical model, which FlyGym parses and re-rigs. Two things
are taken directly:

- `vendor/pattern_generators.py` — `WingBeatPatternGenerator`, vendored verbatim
  from `flybody/tasks/pattern_generators.py` @ d015e9b, with the two constants it
  imported inlined so it needs only numpy.
- `fly/wing_fluid.py` — the wing fluid/inertial geom sizes, positions and
  orientations, copied from `flybody/fruitfly/assets/fruitfly.xml` and scaled
  cm→mm.

> Vaxenburg, R., et al. (2025). A whole-body model of *Drosophila* with precise
> neuromuscular connectivity. *Nature*.
> <https://doi.org/10.1038/s41586-025-09029-4>

## connectome-sim
Consumed as a git submodule; carries its own `THIRD_PARTY.md` covering the
MaleCNS v1.0 dataset (CC-BY-4.0) and the Shiu et al. LIF framework (MIT).

## flappy-haltere
Not a dependency, but `fly/circuit.py`'s population selection follows its
`flappy/circuit.py` and `flappy/fly_regions.py`, and its haltere inverse-dynamics
model is the intended source of the haltere joystick.
