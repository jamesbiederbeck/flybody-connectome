# flybody-connectome

A tethered *Drosophila* body, driven by the MaleCNS v1.0 connectome. Rendered
compound-eye input feeds modeled neural dynamics; decoded activity sets wingbeat
frequency and steering deviation on a MuJoCo fly.

**Status: the loop is closed, but there is no visual information in it yet.** The
arena is empty, so the fly sees a uniform field and the frozen-vision control
reproduces the live run exactly. Wingbeat and steering currently vary because of
the connectome's own left/right asymmetry, not because the fly is seeing
anything. Read "Is vision reaching the wings?" below before drawing conclusions.

## The loop

```
FlyGym eye cameras  ->  721 ommatidia/eye  ->  registered onto connectome columns
  ->  NativeBrain (166,700 neurons, 25,582,938 edges)
  ->  DNp20 right-minus-left + DNpe017 rate
  ->  wingbeat frequency + steering deviation
  ->  wing actuators, on top of a wingbeat pattern generator
```

The brain runs at ~30 Hz; the wingbeat pattern generator and physics run at 10 kHz.
`Brain.dt` is pinned at 0.1 ms and the graph has 25.6M edges, so stepping the
connectome per physics step is not affordable — the decoded action is held
constant between brain updates. The timescale separation is roughly right anyway:
a fly beats its wings ~218 times a second under steering commands that change far
more slowly.

## What actually connects

This is the central measured result, and it shaped the design.

Driving the retina and reading every population after 2 s of simulated time:

| population | cells | spiking |
| --- | ---: | ---: |
| R1–R6 photoreceptors | 3,335 | 3,335 |
| lamina | 7,114 | 5,299 |
| DNp20 (descending) | 2 | **2** |
| DNpe017 (descending) | 2 | **2** |
| DNa02 / DNp09 / MDN | 8 | 0 |
| **all VNC motor neurons** | **708** | **0** |
| wing muscle MNs (`subclass=wm`) | 67 | 0 |
| DLM power MNs | 10 | 0 |
| b1/b2/hg1 steering MNs | 6 | 0 |

**Vision reaches the descending neurons and stops there.** Not one of the 708 VNC
motor neurons fires from retinal input. The wing motor pool is reachable only by
injecting current into haltere afferents directly — with a fresh brain and
haltere current ~8, 340 of 708 VNC motor neurons become active and the wing
muscles fire ~2,900 spikes over 1 s.

So a wing command cannot be read off the motor neurons where it anatomically
belongs. `controls.py` therefore defaults to `source="descending"`, decoding the
cells visual input actually reaches. `source="motor"` is kept because it is the
anatomically right target and because the haltere-driven case is exactly the
joystick this project is heading for — but on its own it produces silence.

This also explains why the sibling `flappy-haltere` project is built around
haltere stimulation rather than visual drive.

Two caveats on the haltere result: the response is **non-monotonic** in injected
current (DLM spikes fall from ~864 at amplitude 8 to ~187 at 30, as more
inhibition is recruited), so "more current" is not "more flight"; and an earlier
sweep that reused one brain across amplitudes was confounded by carried-over
state. Measure with a fresh brain per condition.

## Are the halteres wired up?

**No.** The model has halteres; the connectome has haltere afferents; nothing
joins them.

| link | state |
| --- | --- |
| haltere bodies, joints, geoms in the model | present (`{l,r}_haltere`, `c_thorax-*-haltere-pitch`) |
| haltere actuators | present, but never commanded -- only the wing actuators are written |
| haltere motion during flight | **3e-06 rad** over 44 wingbeats; they do not counter-oscillate |
| sensors anywhere in the model | **none at all** (`nsensor == 0`) |
| what drives the 205 connectome haltere afferents | a scalar derived from thorax angular velocity, host-side |

So nothing measures a Coriolis force, because nothing is moving and there is no
sensor to measure it with. What `circuit.proprioceptive_stimulation` injects is a
current proportional to how fast the body is rotating -- an engineered stand-in
for what a haltere would report, not a haltere.

Tethered, the thorax is welded, so that signal is identically zero and the
pathway is inert. `--haltere-gain` therefore does nothing in the current setup.
It becomes real either in free flight, or as soon as the drive is fed from an
external 3-vector -- which is the point of taking one: a phone IMU and an
airframe supply the same shape.

Wiring them properly means, in order: drive the haltere actuators antiphase to
the wings so they actually beat; add sensors to the model (there are none, so
this is from scratch); and derive afferent drive from haltere deflection rather
than from body rotation. Until then, treat every haltere result as an injected
stimulus, not a measurement.

## Is vision reaching the wings?

Because the wingbeat pattern generator keeps the wings beating regardless, "it
flapped" proves nothing. The control is to freeze the retinal input and compare:

```sh
python -m fly.play --ticks 300                    # live
python -m fly.play --ticks 300 --frozen-vision    # control
```

**Current result: identical, to the last decimal.** That is correct and
expected — `TetheredWorld` is an empty scene, so the live frames are already
constant. It means the visual channel carries no information yet, not that the
wiring is broken. Giving the arena visual structure (a patterned surround, a
drifting grating, a looming disc) is the next step, and this control is how we
will know it worked.

## Accepted approximations

Logged here and in `AGENTS.md` so they are not mistaken for settled science.

**1. The ommatidia registration is a fit between two different animals.** The
connectome's columns come from MaleCNS v1.0 (male); FlyGym's 721-ommatidium
lattice comes from a female micro-CT scan. `retina_map.register` fits centre,
scale, rotation and chirality and reports its residual — currently ~0.038 in
units where the eye has unit radius, about half the lattice spacing. 300 columns
register on the left eye and 525 on the right.

**2. The connectome's eyes are lopsided.** 1,107 mapped receptors on the left
against 2,228 on the right — a property of the reconstruction, not of the fly.
Any left-minus-right steering signal inherits that bias, and under uniform
illumination it is the main thing driving the decoder.

**3. The wingbeat comes from a pattern generator, and the obvious fix is the
wrong one.** *Drosophila* is an asynchronous flier: the DLM/DVM power muscles are
stretch-activated and oscillate at the thorax's mechanical resonance while their
motor neurons fire an order of magnitude slower. The per-beat rhythm is genuinely
not neurally patterned, so something standing in for myogenic oscillation is
correct — driving wing position from per-spike DLM activity would model the fly
as a *synchronous* flier and be less faithful, not more. What is a kludge is the
form: prescribed kinematics replayed at a commanded frequency rather than a
simulated resonance, and with no base pattern file it is a bare sine that
upstream's own docstring calls "not a substitute for a realistic base wing
pattern". Follow-ups in order: fetch the measured base pattern from figshare;
then replace kinematic replay with a resonance model.

**4. FlyGym's FlyBody support is officially experimental** — "the API may change
in future releases, and not all features available for the default NeuroMechFly
model are currently supported". We depend on it anyway because a rigged flybody
with placed eye cameras and a working ommatidia pipeline is worth the churn risk.
FlyGym is pinned exactly and `tests/test_fly_body.py` re-checks every structural
assumption on every bump.

**5. FlyGym drops the wing fluid geometry.** Its FlyBody has only
`{l,r}_wing_{brown,membrane}`; upstream flybody also carries zero-mass
`wing_*_fluid` and `wing_*_inertial` ellipsoids that shape the wing's interaction
with the fluid medium. `fly/wing_fluid.py` re-adds them from the upstream XML.
Neither model enables MuJoCo's *per-geom* ellipsoid fluid model — both rely on
the global medium — so this restores an interaction volume rather than switching
physics. Whether flight wants `fluidshape="ellipsoid"` is open;
`build(ellipsoid_fluid=True)` turns it on for experiments.

**6. Haltere input is engineered current injection**, not modeled campaniform
transduction. Real afferents encode Coriolis forces on a beating haltere with
stroke-locked spike timing; we inject a scalar current host-side before the
audited kernel runs. Same caveat `flappy-haltere` makes about its own drive.

## Setup

Python 3.12. One environment runs the engine, FlyGym and MuJoCo together; see
`requirements.txt`.

```sh
git submodule update --init --recursive
python -m pip install -r requirements.txt
python -m connectome_sim.build_kernel
```

Then place the MaleCNS inputs under `connectome_data/malecns_v1/` and build the
graph — see `connectome_sim/README.md`:

```sh
python -m connectome_sim.prepare
MUJOCO_GL=egl python -m fly.play --ticks 300
```

FlyGym downloads ~140 MB of meshes on first use and caches them.

## Layout

| Path | Contents |
| --- | --- |
| `fly/body.py` | FlyGym FlyBody + TetheredWorld construction |
| `fly/retina_map.py` | Hex-lattice registration; pale/yellow channel collapse |
| `fly/circuit.py` | Population selection: descending, power, steering, haltere |
| `fly/controls.py` | Rate → continuous wing actuator decoder |
| `fly/wing_fluid.py` | Re-adds the wing fluid/inertial geoms FlyGym drops |
| `fly/play.py` | Headless run loop and JSON report |
| `vendor/` | Wingbeat pattern generator, vendored from flybody |
| `connectome_sim/` | The engine, as a submodule |

## License and attribution

Original code is MIT (`LICENSE`). See `THIRD_PARTY.md` — the body model, the
vision pipeline and the pattern generator are other people's work.
