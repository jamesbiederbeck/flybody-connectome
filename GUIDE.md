# Running and extending a connectome-driven body simulation

Notes from building this one. The specifics are FlyGym + MuJoCo + a LIF
connectome, but most of what follows is about a general shape: a biological
network with its own fixed timestep, driving a physics model with a different
one, where neither side will tell you when the coupling is wrong.

Read `AGENTS.md` first — it lists the constraints that have already cost
someone a wrong answer. This is the how-to; that is the don't.

## The shape of the problem

```
render eyes  ->  sample receptors  ->  brain.step  ->  decode  ->  actuators  ->  physics
   30 Hz            30 Hz              30 Hz          30 Hz       10 kHz         10 kHz
```

Two clocks. The brain's is fixed by the engine (`Brain.dt` is pinned at 0.1 ms
and `engine.py` raises if you change it); the physics clock is fixed by the
model (1e-4 s). A 166,700-neuron, 25.6M-edge graph cannot be stepped per physics
step, so the decoded action is **held constant** between brain updates while the
pattern generator and physics run on.

That hold is the single most important structural decision in the loop, and it
is where most coupling bugs live. Write down, for every signal crossing between
the clocks, whether it is held, integrated, or resampled — and then check the
*achieved* value rather than trusting the commanded one. See "Rate traps".

## Running it

One Python 3.12 environment runs the engine, FlyGym and MuJoCo together.

```sh
git submodule update --init --recursive
python -m pip install -r requirements.txt
python -m connectome_sim.build_kernel        # compiles the C++ LIF kernel
python -m connectome_sim.prepare             # builds outputs/.../graph.npz
MUJOCO_GL=egl python -m fly.play --ticks 300
MUJOCO_GL=egl python -m fly.render --world flat --ms 200
```

`MUJOCO_GL=egl` must be set **before the process starts**, or before `mujoco` is
imported — it picks its GL backend at import time, and headless it will
otherwise select GLFW and die on a missing `DISPLAY`. Setting it in a test file
after `import mujoco` is too late; `tests/test_fly_body.py` sets it above the
imports for exactly this reason.

FlyGym downloads ~140 MB of meshes on first use and caches them.

## The measurement discipline

This is the part that generalises furthest, and the part that is easy to skip.

**Ask what the negative control looks like before you run anything.** In a
simulation you control every input, which means you can almost always produce
motion — and motion is not evidence. Here the pattern generator keeps the wings
beating with the connectome disconnected, so "it flapped" proves nothing and
"it stayed up" would prove nothing either. The controls that do carry
information: freeze the visual input and compare (`--frozen-vision`), hold the
wings still and compare, zero the gain and compare.

**Change one thing at a time, and rebuild state between conditions.** Both
`Brain` and `MjData` carry state across a run. Reusing one instance across
conditions has already produced a confidently wrong result in this project — a
haltere current sweep that reported the pathway dead at low amplitude and at
threshold at high, when in fact a fresh brain per condition shows it strong from
amplitude 8 and *decreasing* thereafter.

**Preserve nulls.** A control that reproduces the live run to the last decimal is
a finding about the setup, not a failure to be tuned away. The frozen-vision
control matching exactly is how we know the arena is empty; deleting that line
and adding a scene would have quietly converted a known-empty condition into an
unexamined one.

**Distinguish measured from inferred in the writeup.** "Lift is zero across three
wing-geometry variants" is measured. "Therefore the stroke pattern is the cause"
is an inference by elimination, and stays an inference until the alternative
pattern is actually run. Write both, labelled.

## Unit traps

Physics engines are unit-agnostic. Nothing checks you, and a wrong unit produces
a plausible simulation rather than an error.

The one this project hit: FlyGym's flybody model is in millimetres and converts
gravity (`-981 cm/s² x10 -> mm`, per its own comment) and every body density
(0.713 g/cm³ -> 7.13e-4 g/mm³) — but leaves `option/density` and
`option/viscosity` at their centimetre values. 0.00128 g/cm³ is air; 0.00128
g/mm³ is denser than water. The fly is otherwise correct at 1.0 mg with a 1.4 mm
wing, so **as shipped it flaps in a liquid, sinks only 2.8 mm in 200 ms, and
looks like it is flying**.

How to catch this class of bug:

- **Convert every global to SI by hand once, and sanity-check the number.**
  Density in g/mm³ times 1e6 is kg/m³. Air is 1.2; water is 1000. This takes a
  minute and would have caught it immediately.
- **Run the dead-body control.** A model with no actuation should fall at *g*.
  Compare `xpos[2]` against `z0 - 0.5*g*t^2`. Ours fell at a terminal ~56 mm/s,
  which is not air, and that was the tell — the *no-flap* run, not the flapping
  one.
- **Check masses independently.** Total body mass matching the real animal (1 mg)
  is what told us the geometry and body densities were right and isolated the
  fault to the medium.

## Rate traps

**A prescribed pattern has its own timestep.** The vendored wingbeat generator
advances one `dt_ctrl` (2e-4 s) per call. Called once per 1e-4 s physics step it
plays at double speed — a 436 Hz wingbeat. The commanded trajectory looks
identical either way. The only thing that reveals it is comparing commanded
against **achieved joint `qpos` amplitude**: 2.8 rad collapses to 1.2 rad
because the position servos cannot track the faster target. Make that comparison
a standing check, not a debugging step.

**Position actuators are servos, not prescriptions.** Writing a value to
`data.ctrl` requests a position; what the joint does depends on gain, inertia and
load. At flapping frequencies the gap is large and direction-dependent (ours
overshoots: 2.8 rad achieved against 2.1 commanded). Never report a commanded
number as if it were achieved.

## Reading state back out

**Do not slice `qvel` for body velocity.** `qvel[3:6]` is the angular velocity of
the root freejoint *only if there is one*. In a tethered world there is not, and
those three dofs are whatever joints happen to be indexed there — here, the
proboscis. That bug fed mouthpart velocity into the haltere afferents and read
zero only because the mouthparts happened to be still. Use
`mj_objectVelocity(model, data, mjOBJ_BODY, id, out, 1)`, which is correct with
or without a freejoint and survives untethering.

**Fluid forces accumulate in `qfrc_passive`.** That is where lift and drag land.
Two cautions, both learned the hard way:

- A falling body sees an upward drag that is indistinguishable from lift in the
  same array, tending to exactly 1.0x body weight at terminal velocity no matter
  what the wings do. Measure lift with gravity zeroed.
- Average over **whole cycles only**. Peak in-beat force here is ~4x body weight
  against a mean of ~0, so a partial cycle biases the mean by more than the mean.

**Check `nsensor` before assuming a sensor exists.** This model has zero. Bodies,
joints, geoms and even actuators can all be present for a structure that is
measuring nothing and being commanded by nothing — the halteres are exactly that.

## Extending it

**A new world.** Subclass or instantiate a FlyGym world and pass it to
`body.build`. Note that each fly class has its own contact-bodies enum: the base
world's default belongs to NeuroMechFly and a FlyBody rejects it, so name the
preset explicitly. A tethered world has no freejoint (`nq` 102); a free one adds
7 qpos and 6 qvel (`nq` 109) — do not propagate 7 to an `nv` assertion.

**A new readout population.** Select at runtime from the annotation table rather
than hardcoding ids:

```python
from connectome_sim.physiology.common import annotations
ann = annotations(brain.ids)
rows = np.flatnonzero(ann.type.isin(["DLMn a, b", "DLMn c-f"]).to_numpy())
```

Ids are graph-local and change when the graph is rebuilt; types do not. Put new
selections in `fly/circuit.py` beside the existing ones, and write a test using
the synthetic-brain fixture in `tests/conftest.py` so it runs without the 25.6M
edge graph.

**A new input pathway.** Current injection goes in through
`brain.step(..., stimulation=(indices, amplitudes))`. Two constraints: only
`NativeBrain`, `GPUBrain` and `MemoryBrain` accept it — the pure-numba `Brain`
does not — and it is host-side injection *before* the audited kernel runs, so it
is an engineered input and must be labelled as one wherever it surfaces. Keep the
drive function's signature in terms of a physical quantity (an angular-velocity
vector, say) rather than anything MuJoCo-specific, so the source can later be a
phone IMU or an airframe without touching the pathway.

**A new decoder output.** `fly/controls.py` converts spike counts to continuous
values through a vectorised EMA matching the engine's own `NeuralControls.decode`
time constant. Every gain in it is an engineering choice; say so in the
docstring. When behaviour is strange, suspect these before suspecting the
connectome.

**Rendering anything.** Pass `make_renderer` into the loop rather than
reimplementing it. `play.run` takes a `callable(mj_model) -> renderer` and calls
`render_as_needed(data)` inside the substep loop, so the video and the JSON
report come from the same code path — and you can prove it by checking the run
reproduces its own numbers with rendering on.

## Before you believe a result

- Did a control run, and did it differ from the live run?
- Is the number measured or inferred? Which?
- Were units checked against an SI sanity value?
- Commanded or achieved?
- Fresh state per condition?
- Averaged over whole cycles?
- Does anything in the claim depend on a sensor, joint or actuator you have not
  confirmed exists in the compiled model?
