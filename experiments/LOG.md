# Experiment log

Newest first. Each entry: what was asked, what was run, what came back, and what
it changed. Negative results and corrections to earlier entries stay in — an
entry is never edited to look better in hindsight, it gets a follow-up.

Conventions used throughout: a fresh `NativeBrain` (or a verified state reset)
per condition, because both brain and physics state carry; every claim labelled
measured or inferred; and a stated control for anything that could be produced
by the setup rather than the thing being measured.

---

## 2026-09-19 — Flight: four causes ruled out, still no lift

Continuing from the wing-pattern result below. Each row uses the measured
figshare pattern; lift is the `--hover` protocol (gravity zeroed, whole beats).

| configuration | tracking yaw/roll/pitch | lift / weight | peak |
| --- | --- | --- | --- |
| flygym as-is | 2.26 / 1.16 / 0.94 | -0.0174 | 4.05 |
| best of a 12-point gain x damping sweep | 1.29 / 1.00 / 0.99 | **+0.0062** | — |
| + ellipsoid fluid, upstream fluidcoef | 2.11 / 0.97 / 0.94 | -0.0006 | 9.71 |
| upstream params **as written** (gain 18) | 0.11 / 0.06 / 0.11 | +0.0002 | 0.01 |
| upstream params **converted cm->mm** (gain 1800) | 0.99 / 0.82 / 0.88 | -0.0052 | 0.38 |
| converted + ellipsoid fluid | 0.98 / 0.83 / 0.87 | -0.0113 | 2.41 |
| gain 3600 + ellipsoid (best tracking) | **1.03 / 1.02 / 1.07** | -0.0043 | 3.43 |

**Ruled out: the wing pattern, servo tracking, actuator gain/stiffness/damping,
and the ellipsoid fluid model.** Every one changes force *magnitude* — peak
ranges from 0.38 to 9.71 body weights across the table — and none produces net
lift. A fly needs 1.0; the best result anywhere is +0.006.

**What upstream actually does** (`flybody/tasks/base.py:270-322`), which flygym's
FlyBody never receives: wing gain 18, stiffness 0.01, damping 0.00777, and
`geom.fluidshape = 'ellipsoid'` with `fluidcoef = [1.0, 0.5, 1.5, 1.7, 1.0]` on
every `*fluid*` geom. `fluidcoef[3] = 1.7` is the Kutta lift coefficient, so
without that assignment the wings have drag and no lift term at all. FlyGym ships
the FlyBody rigged but not configured for flight.

**Another cm/mm trap.** Upstream is in centimetres and torque scales x100, so
gain 18 means 1800 in flygym's millimetre model and damping 0.00777 means 0.777.
Applied as written they collapse tracking to 0.10. FlyGym converted the joint
stiffness (0.01 x 100 = 1.0, which is what it ships) and not the rest — the same
partial-conversion pattern as the fluid medium.

**Still untested, and now the leading suspects.** Both are geometric rather than
parametric, which fits a failure that survives every magnitude change:

1. The re-added wing fluid ellipsoid's *orientation*. `fly/wing_fluid.py` copies
   quaternions verbatim from upstream's XML, but flygym's wing body frame may
   not match upstream's, in which case the lift vector points somewhere useless.
2. Whether flygym's yaw/roll/pitch joint axes are the axes the recorded pattern
   was authored against. Commanded ranges match the pattern exactly, which
   confirms the WPG is faithful but says nothing about whether flygym's "yaw" is
   upstream's "yaw".

**The decisive experiment is to run upstream flybody itself.** It is checked out
at `~/code/playground/drosophila/flybody`. If its own flight task produces lift
with this pattern, our port is broken and the diff localises it; if it does not,
the premise that this model flies in MuJoCo is wrong and the whole flight goal
needs rethinking. That separates the two possibilities in one run and should
come before any further parameter search here.

---

## 2026-09-19 — The measured wing pattern does not fix flight (`fly/render.py --wing-pattern`)

Downloaded `datasets_flight-imitation.zip` (12.9 MB, md5 verified) from the
flybody figshare record; it contains `wing_pattern_fmech.npy`, shape (500, 3),
the measured base wing kinematics. Vendored to `assets/`.

| | lift / weight | peak / weight |
| --- | --- | --- |
| bare sine | -0.0177 | 4.17 |
| **measured pattern** | **-0.0158** | 4.51 |

**No change.** The flight write-up named the bare sine as the cause of zero lift
and explicitly labelled that an inference by elimination rather than a
measurement. It has now been measured, and it was wrong.

**A better candidate: the wing servo overshoots.** Commanded against achieved
joint range, driven with the measured pattern at 218 Hz:

| dof | commanded | achieved | ratio |
| --- | --- | --- | --- |
| yaw (the stroke) | -0.84 .. +1.41 | **-2.32 .. +2.74** | **2.26** |
| roll | -0.32 .. +0.15 | -0.40 .. +0.15 | 1.16 |
| pitch | -0.56 .. +2.14 | -0.61 .. +1.93 | 0.94 |

FlyGym drives the wings with position actuators at gain 300/200/100; upstream
flybody uses gain 18 with the spring and damping in `_WING_PARAMS`. At 218 Hz
that servo rings and the wing sweeps 2.26x further than commanded, so the stroke
kinematics are wrong regardless of which base pattern is supplied — which is
why swapping the sine for the measured data changed nothing. Lift depends on the
yaw/pitch phase relationship within the stroke, and that relationship is being
distorted by the actuator, not by the pattern.

Next: bring achieved into line with commanded (lower the yaw gain, or move to
force actuators with upstream's spring/damping) and re-measure lift. Until the
servo tracks, no pattern experiment means anything.

**A methodology slip worth recording.** The first comparison returned identical
numbers to four decimals for both patterns, because the `--wing-pattern` flag
never reached `render()`: a string replacement missed its target and dropped the
argument silently. Caught only because identical-to-four-decimals is
implausible. The report now echoes which pattern was used, so a dropped argument
is visible in the output rather than inferable from suspicious agreement.

---

## 2026-09-19 — Leave-one-out refutes the seven-cell claim (`haltere_leave_one_out.py`)

**198 individually-silent afferents are not collectively silent.**

| set | n | 8 mV | 14 mV | 20 mV |
| --- | --- | --- | --- | --- |
| all_205 | 205 | 1061 | 653 | 597 |
| potent_7 | 7 | 894 | 895 | 1022 |
| **silent_198** | 198 | **892** | 724 | 634 |

Each of those 198 cells produces zero motor spikes driven alone; together they
produce as much as the seven potent ones. Sub-threshold summation dominates, and
the "interface is seven cells" conclusion from the single-cell sweep is
**withdrawn**. This was the caveat recorded with that result, and testing it was
the right call.

**What survives, and is strengthened: the pathway is one-dimensional.** The
response pattern of `silent_198` and `potent_7` are the same vector — cosine
0.9999, 0.9996, 0.9987 at 8/14/20 mV — symmetric power muscles, essentially
nothing on b1, b2 or hg1. So it is not that a few cells work; it is that every
subset does the same thing. Three independent subsets now support that, rather
than one analysis of seven cells.

Two further facts: the pathway is **strongly sub-additive** (all_205 = 1061
against potent + silent = 1786, ratio 0.59, falling to 0.36 at 20 mV), and
**non-monotonic in current** (1061 -> 653 -> 597), the effect `AGENTS.md` warns
about, now visible directly.

**Consequence for the joystick.** A multi-axis haltere interface cannot be built
from afferent identity in MaleCNS v1.0 — not because the right cells are
undiscovered, but because every subset drives the same single output mode. The
scalar `norm(omega)` in `proprioceptive_stimulation` is not an approximation to
be improved; it is the true dimensionality of this pathway. If multi-axis
information exists, it has to be carried by timing rather than identity, which
is what the tau = 2 ms result opens.

---

## 2026-09-19 — Single-cell sweep: the interface is seven cells (`haltere_single_cell.py`)

**Superseded by the leave-one-out result above: the seven-cell framing is an
artifact of testing cells one at a time.** The concentration measurement below
is still accurate as stated — it is the conclusion drawn from it that was wrong.

**198 of 205 haltere afferents produce exactly zero motor spikes when driven
alone at 20 mV.** Gini 0.976; the top five cells account for 93% of all
single-cell response and the top ten for 100%.

| body_id | type | side | out-deg | 8 mV | 14 mV | 20 mV |
| --- | --- | --- | --- | --- | --- | --- |
| 101048 | SApp | R | 293 | 0 | 0 | 1037 |
| 136883 | SApp | L | 311 | 0 | 0 | 1018 |
| **946174** | SNpp12 | R | 310 | **611** | 861 | 964 |
| 808963 | SNpp23 | L | 112 | 0 | 0 | 934 |
| 809889 | SNpp23 | R | 107 | 0 | 0 | 479 |
| 801205 | SNpp12 | L | 328 | 3 | 13 | 240 |
| 810009 | SNpp23 | L | 101 | 0 | 0 | 92 |

Every cell of SNpp14, 15, 20, 21, 25, 34, 35 and SNxx25 is individually silent —
45 cells, zero response between them. The 148-cell SApp bulk contributes through
two cells (Gini 0.987 within the type).

**Not a threshold artifact.** Two cells respond at 8 mV and seven at 20 mV:
raising the current fivefold recruits five more cells, not hundreds. And 946174
is uniquely low-threshold, firing 611 spikes at 8 mV where every other cell in
the graph gives 0 or 3.

**It closes the SNpp23 anomaly.** Its left cells total 1,026 spikes against 479
on the right. That 2:1 asymmetry is why antiphase drive failed to cancel for
SNpp23 in the depth-phase run while cancelling for every other pair — predicted
there, confirmed here by an independent measurement.

**What it costs.** The 45-pair antagonist sweep was mostly pairing objects that
cannot respond at all: only pairs containing SNpp12 or SNpp23 could do anything,
which is exactly the pattern observed. "Cluster" is the wrong unit, and the
usable haltere interface for a joystick is about seven named cells, not 205 or
ten clusters.

**The caveat that is not yet tested.** Silent *alone* is not the same as
contributing nothing *in combination*: sub-threshold inputs can sum at a shared
target. The cluster results are consistent with the potent cell dominating
(SNpp12 as a cluster gives 611 at 8 mV, exactly its R cell alone), but additive
sub-threshold contribution has not been measured and would need a leave-one-out
design to rule in or out.

---

## 2026-09-19 — Is the first synapse a bottleneck or a feature? (`haltere_tau_test.py`)

**A simulation bottleneck, and the fix has an optimum rather than a direction.**

| tau_m | corner | afferents z | hop-1 z | motor z | afferent rate |
| --- | --- | --- | --- | --- | --- |
| 20 ms (reference) | 8 Hz | 5.11 | **-0.28** | -1.12 | 43 Hz/cell |
| 5 ms | 31.8 Hz | 2.39 | 0.22 | -0.46 | 138 Hz/cell |
| **2 ms** | 79.6 Hz | **11.83** | **5.25** | **3.08** | **219 Hz/cell** |
| 0.73 ms | 218 Hz | 1.31 | 0.31 | 0.58 | 344 Hz/cell |

At tau_m = 2 ms the 218 Hz carrier crosses the first synapse and reaches the wing
motor pool. The wiring does not discard it; the membrane constant does. The
structural argument agreed in advance: convergence onto hop-1 cells is modest
(median 4 afferents each), every synapse carries the same fixed 1.8 ms delay,
and hop 1 is 100% excitatory, so afferents driven in phase spike synchronously
and their inputs arrive synchronously — summation preserves phase and nothing
structural is available to destroy it.

**Locking peaks where firing rate matches the carrier.** At tau = 2 ms the
afferents fire 219 Hz against a 218 Hz drive: one spike per cycle, the ideal
condition. At 0.73 ms they fire 344 Hz — more than one spike per cycle, so
spikes land at several phases and locking dilutes, with the 2.2 ms refractory
ceiling at 455 Hz. At 20 ms they fire 43 Hz, one spike per five cycles. So
"faster tau" is not the intervention; there is an optimum, and it moves with
drive level, since saturation depends on how hard the cells are driven. A
fast-tau subnetwork should be tuned so its relay cells fire near wingbeat
frequency, not as fast as possible.

**This run is the second attempt; the first was void.** See the bug below.

---

## 2026-09-19 — A bug I introduced, and what it invalidated

`Brain.step` gained a `stimulation` argument in the morning's tau commit, and it
injected the current without adding those cells to the active set. The engine
only integrates active cells, and that set is seeded with retina/lamina/sugar
alone — so injected current into any sensory afferent was silently ignored until
some synapse happened to recruit the cell. `kernel.cpp:26` awakens any cell
whose drive changed; the numba path did not.

Measured on 205 haltere afferents at 12 mV for 100 ms: **native fired 829 of
them, numba fired 1.** After the fix both fire 829 (totals 37,466 against
37,469 — close, not identical).

**Invalidated:** the first tau sweep, which ran on the numba backend. Its two
anomalies were both symptoms — zero spikes at tau = 0.73 ms, and a
non-monotonic dip at tau = 5 ms — which is why they were worth chasing instead
of explaining away. **Unaffected:** every other experiment in this log, all of
which used `NativeBrain`.

**Nothing to upstream.** `stimulation` did not exist on the numba `Brain.step`
before that commit, so doomfly cannot have the bug; every path there that
injects current goes through the correct C++ kernel.

**Worth keeping:** the two backends now agree to 3 spikes in 37,466 on an
identical stimulated run. That comparison would have caught this immediately had
it been run when the parameter was added.

---

## 2026-09-19 — 218 Hz by depth (`haltere_depth_phase.py`)

**The bottleneck is the first synapse, not the afferents.** Every cluster
phase-locks to a 218 Hz drive in its own spike train; not one passes it on.

| cluster | 218 Hz depth0 | depth1 | 10 Hz depth0 | depth1 |
| --- | --- | --- | --- | --- |
| pooled_all | 27.77 | **0.27** | 14.69 | 5.42 |
| SApp | 14.12 | **0.84** | 25.64 | 13.05 |
| SNpp12 | 6.97 | **-0.89** | 6.20 | 1.88 |
| SNpp23 | 42.04 | **0.20** | 7.73 | 2.02 |
| SNpp20 | 26.15 | — | 2.10 | — |

At 10 Hz the first synapse passes roughly half the locking (25.64 -> 13.05). At
218 Hz it passes none, in every cluster, including SNpp23's z = 42 collapsing to
0.2. This is the sharpest localisation of the problem so far, and it names the
intervention: the ~1,443 hop-1 relay cells are where a faster membrane constant
would have to go, not the afferents.

**An anomaly worth following: SNpp23 antiphase does not cancel** (depth0 z =
25.7, against 0.15 for pooled_all, -0.33 for SNpp12, 1.07 for SApp). Antiphase
cancellation in a pooled L+R readout requires the two sides to contribute
equally. SNpp23's three left and three right cells evidently do not — the same
class of asymmetry found inside SNpp12, where one of two cells carried the whole
cluster.

`SNpp20` shows `None` at depths 1 and 3: no spikes at all in those readouts,
consistent with its silence in the DC sweep.

**Method note.** The depth-2 column is uninterpretable — see below — and the
motor column reproduced the standalone phase experiment to the digit (4.61),
which is a useful agreement between two separately written scripts.

Reads out at four depths (stimulated afferents, hop-1 targets, hop-2 targets,
wing motor) rather than only at the motor pool, so a 218 Hz null says *where*
the modulation dies rather than only that it is absent. Depth 0 is a built-in
positive control: modulation is present in the stimulated cells by construction.
Every cluster also runs at 10 Hz, because a cluster-level null at 218 Hz is
uninterpretable on its own — single clusters showed nothing even at 10 Hz where
the pathway demonstrably follows.

**A readout flaw found in the first row, recorded before the rest arrives.**

    pooled_all 10 Hz in_phase   depth0: 14.69  depth1: 5.42  depth2: -0.31  motor: 4.61

Depth 2 pools ~60,000 cells into one spike train. They sit at different path
lengths, so their modulation arrives at different phases and cancels in the sum:
the pooled trace reads as chance even if every constituent cell is modulated.
**The depth-2 column is not interpretable** and the meaningful comparison is
depth 0 → depth 1 → motor. Fixing it properly would mean per-cell vector
strength averaged over cells, not vector strength of the pooled train.

The rest is sound: depth 0 confirms the drive, the first synapse attenuates
~3×, and the motor value reproduces the standalone phase experiment exactly
(4.61 under identical conditions), which is a useful consistency check between
two separately written scripts.

---

## 2026-09-19 — Johnston's organ, first pass (`jo_tracing_check.py`, `jo_potency.py`)

**A claim checked and rejected before building on it.** A suggestion arrived that
linear acceleration, gravity and wind should be read from the JO-A array
(JO-A1–A4). MaleCNS's own `subclass` labels say the opposite: JO-A is
**auditory 49 cells to 1**, while the wind/gravity population is JO-E (EV 176,
ED 91) and JO-C (CL 19, CM 23). That matches Kamikouchi et al. 2009 and Yorozu
et al. 2009 — JO-A/B are the phasic sound-and-vibration subgroups, JO-C/E the
tonic ones responding to sustained deflection. JO-A1–A4 is also only 26 cells.
Driving JO-A for gravity would have driven the auditory pathway.

**Tracing check first, because all 672 JO cells are `RT Hard to trace`** — the
dataset's lowest tier, with no Reviewed subset to stratify against. Structural
proxies instead, against the haltere afferents as a positive reference:

| population | n | median out-degree | zero-output |
| --- | --- | --- | --- |
| JO wind_gravity | 475 | 86.0 | 57 (12%) |
| JO auditory | 114 | 38.5 | 29 (25%) |
| haltere afferents | 205 | 114.0 | 1 (0.5%) |
| whole graph | 166,700 | 112.0 | 1,220 (0.7%) |

Type labels are structurally real — within-type target overlap 0.097 against
0.024 between types, a ratio of **3.99**, matching the haltere reference's 3.80.
But ~13% of wind_gravity cells are dead ends and arbors are truncated, so
**every potency result is a lower bound**: silence cannot be distinguished from
an unreconstructed axon. And bilateral pairing is unavailable — median L/R
imbalance 0.472, with 16 of 34 types worse than 2:1 — so the haltere design's
reliance on types being near-perfect bilateral pairs does not port.

**The control came back and the wind/gravity result does not survive it.**
Size-matched random draws from other sensory populations (`jo_specificity_control.py`),
at 8 mV, 3 draws each:

| random n | draws | JO group at that size | JO 8 mV | verdict |
| --- | --- | --- | --- | --- |
| 19 | 0, 0, 0 | JO-FD (8) | 2055 | **specific** |
| 19 | 0, 0, 0 | JO-mz (11) | 2865 | **specific** |
| 19 | 0, 0, 0 | JO-CM (30) | 2404 | **specific** |
| 50 | 184, 0, 0 | JO-A (50) | 2121 | **specific** |
| 50 | 184, 0, 0 | JO-FV (70) | 3116 | **specific** |
| 91 | 916, 3903, 0 | JO-ED (91) | 2192 | within random |
| 176 | 2787, 3437, 3537 | JO-EV (176) | 3173 | **within random** |
| 475 | 3507, 3857, 4772 | pooled_wind_gravity (475) | 3498 | **within random** |

JO-EV and pooled_wind_gravity -- the populations this whole line of work was
pointed at -- produce exactly what a random draw of the same size produces. At
n >= 176 the assay is saturated: injecting current into any 176 sensory cells
fills the motor pools, so there is no dynamic range left to distinguish JO from
anything. The earlier claim that "JO reaches the flight motor system harder than
the halteres do" was measuring saturation, not JO, and is withdrawn.

What *is* specific is small: JO-FD produces 2,055 spikes from **8 cells** where
random 19-cell draws give zero; JO-mz 2,865 from 11; JO-CM 2,404 from 30. And
JO-A -- the *auditory* array -- is specifically potent at 50 cells against a
random mean of 61.

Same shape as the halteres: potency concentrated in a few small groups, large
populations indistinguishable from generic ignition. The fix is to leave
saturation -- rerun the large arrays at 4-6 mV or shorter duration, where random
draws are silent and the assay has range.

**Original potency result, superseded by the control above.** Nearly every JO group
drives thousands of motor spikes at 8 mV (unstimulated baseline is 0 in every
pool). Output lands on abdomen (~1,750 spikes across 214 cells) and wing
(~1,400 across 67) — per cell the wing pool is the strongest target, stronger
than the halteres reach it — while neck, the classic gravity/wind postural
output, gets 5–87 spikes across 24 cells.

| group | n | abdomen | wing | legs f/m/h | neck | 8→20 mV |
| --- | --- | --- | --- | --- | --- | --- |
| JO-EV | 176 | 1198 | 1651 | 314/387/330 | 87 | 3173→4132 |
| JO-ED | 91 | 1472 | 1242 | 306/315/260 | 58 | 2192→3758 |
| JO-B | 88 | 1174 | 1096 | 135/257/230 | 48 | 699→3047 *graded* |
| JO-CL | 19 | 72 | 195 | 0/4/56 | 6 | 0→389 *graded* |
| JO-A (auditory) | 50 | 1145 | 1082 | 36/135/145 | 20 | 2121→2636 *flat* |
| pooled wind_gravity | 475 | 1755 | 1391 | 457/377/281 | 67 | 3498→4465 |

Two problems with reading this as "JO drives the motor pools".

**Most groups are flat in current** — JO-A goes 2121 → 2636 from 8 to 20 mV, and
CM, FD, FV, mz likewise. That is not the haltere signature (sharp threshold,
graded, only 2 of 10 clusters responding), and combined with haltere input
reaching 97% of the brain in three hops it suggests that injecting current into
any large population ignites the network generically. `jo_specificity_control.py`
tests exactly that with size-matched random draws from other sensory
populations; until it returns, this table says nothing specific about JO.
JO-B, CA and CL would survive that control regardless, being genuinely graded.

**An entire side of the auditory population is unreconstructed.**
`pooled_auditory_R` (52 cells, 27 with zero outputs) gives **exactly 0 at every
current** while `pooled_auditory_L` (62 cells, 2 zero-output) gives ~2,500.
`JO-unclear` (102 cells, 57 zero-output) is 0 throughout. An L/R comparison here
would read reconstruction damage as biology.

---

## 2026-09-19 — In-phase vs antiphase drive (`haltere_phase_pairs.py`)

**The pathway sums bilateral haltere input rather than comparing it.**

Two groups driven sinusoidally with a relative phase offset; total injected
current identical across phases, so any difference is a phase effect. 10 Hz is a
positive control (the MTF says the pathway follows there); 218 Hz is the
question.

| pair | 0° in-phase | 90° quadrature | 180° antiphase |
| --- | --- | --- | --- |
| all halteres L\|R @ 10 Hz | **z = 4.61** | z = 3.61 | **z = −0.56** |
| SNpp12\|SNpp23 @ 10 Hz | **z = 4.25** | z = 1.44 | **z = −0.52** |
| every pair @ 218 Hz | −0.76 … −0.05 | −1.16 … −0.37 | −0.74 … +0.15 |

Monotonic in phase offset, in two independent pairs: in-phase locks strongly,
quadrature partially, **antiphase not at all**. That is a cancellation
signature. The convergence point computes something like L+R, so a pitch-like
in-phase signal survives and a roll/yaw-like antiphase signal cancels to a DC
level carrying no modulation.

This is the mechanism behind the DC sweep's null. Antisymmetric drive did not
fail to produce a *lateralised* response; it fails to produce a *modulated* one
at all, because the two sides cancel where they converge. Symmetric power was
1.000 in all 24 trials regardless of drive phase.

At 218 Hz nothing, anywhere, as predicted from the 8 Hz corner. The prediction
was recorded before the run.

**Single small clusters show nothing at any phase** (SNpp12_L\|R, SNpp23_L\|R:
z from −0.4 to 1.02). The effect needs the full ~102-cell-per-side population;
one or three cells cannot modulate the pool detectably. So this is a population
result and does not license claims about individual clusters.

---

## 2026-09-19 — Modulation transfer function, corrected (`haltere_mtf.py`)

**Corner between 10 and 30 Hz; nothing above it in any readout.**

The first run reported per-group vector strength without per-group floors, and
I flagged the b1/b2 numbers (r of 0.25–0.63 even at 218 Hz) as uninterpretable.
They were. Each group now gets a chance level computed *within* the trial, from
the same spike train at frequencies it was not driven at, which scales with
spike count by construction.

| Hz | pooled r | pooled z | control z | power_L z | power_R z | b1/b2/hg1 z |
| --- | --- | --- | --- | --- | --- | --- |
| 5 | 0.156 | **5.3** | −0.0 | **5.6** | **5.4** | −2.5 … 1.9 |
| 10 | 0.144 | **4.6** | −0.6 | **4.7** | **4.0** | −0.3 … 2.3 |
| 30 | 0.026 | −0.2 | −1.4 | −0.1 | −0.9 | −1.8 … 1.3 |
| 60–400 | 0.015–0.051 | −1.2 … 0.8 | −1.3 … −0.4 | −0.7 … 0.4 | −1.3 … 1.5 |

The apparent fast following in the steering muscles was small-N artifact:
**b1_L, b1_R, b2_L and b2_R fire 5 spikes each** in a 1000 ms trial, and chance
vector strength at 5 spikes is ~1/sqrt(5) = 0.45 — exactly the range reported.
With proper floors, only the power muscles (886 and 907 spikes) lock, only at
5–10 Hz. The speculation that b1 might follow faster, and the Fayyazuddin &
Dickinson connection I hung on it, is **refuted**.

Corner matches 1/(2*pi*tau) = 8.0 Hz for tau = 20 ms, so the membrane constant
is the binding constraint, not the balanced convergence. Following a 218 Hz
wingbeat would need tau ~= 0.73 ms — shorter than the 1–5 ms of fast
interneurons, and worth putting beside Fox et al.'s measured 0.81 ms spike-timing
jitter in haltere afferents: the biology works at that timescale through precise
spike timing, not through an implausibly leaky membrane.

**Question.** Does a sinusoidal modulation of haltere drive reach the wing motor
pool, and up to what frequency? A wingbeat is 4.59 ms / 218 Hz.

**Why this and not the impulse test.** The impulse measurement below asked
whether a brief input *from rest* can drive firing. It cannot, but from rest the
threshold dominates and that says little about a flying animal. Here a
supra-threshold baseline (12 mV) holds the pool firing and the sinusoid is a
perturbation on top — ongoing activity linearises the threshold. This is the
regime a beating haltere actually produces.

**Metric.** Vector strength of binned wing-motor spikes at the modulation
frequency, each paired with an unmodulated control at the same baseline that
gives the chance floor. Sweep 5–400 Hz.

**Decides.** Whether lowering the membrane time constant is worth doing, and by
how much. Result pending.

---

## 2026-09-19 — Antagonist-pair sweep, corrected (`haltere_axis_pairs.py`)

**Question.** Do haltere clusters form antagonist pairs carrying a symmetric
(pitch-like) or antisymmetric (roll/yaw-like) signal? Four sign conditions per
candidate pair; conditions 3 and 4 are the sign-negations of 2 and 1, which is
the falsification test.

**Correction to the first run.** The first sweep used baseline 11 ± 3 mV, so its
"low" condition sat at 8 mV — *below* the 8–10 mV recruitment threshold that
flappy-haltere's cluster sweep had already measured. The four conditions were
on/off, not a sign flip. Rerun at 12 ± 2 (10 and 14, both supra-threshold).

**Result: no antagonist structure and no lateralisation.**

| | 11 ± 3 (confounded) | 12 ± 2 (corrected) |
| --- | --- | --- |
| silent pairs | 12/45 | 14/45 |
| pairs passing both criteria | 0 | 2, both noise (ref 15 and 21 spikes) |
| symmetry of the *antisymmetric* condition | ≈1.0 | min 0.851, mean 0.985 |

Across the 16 responsive pairs, antisymmetric drive produces a response that is
85–100% symmetric. Driving left hard and right weakly gives almost exactly the
same bilateral output as the reverse. Sign inversion also proved unreliable once
the confound was removed — the same pair gives `inv_sym = −0.997` and
`inv_anti = +0.997`, which tracks which cluster is driven harder rather than any
push/pull axis.

Every responsive pair contains SNpp12 or SNpp23; all 14 silent pairs contain
neither. Four pairs are byte-identical to another pair, meaning the second
cluster contributes nothing at all.

**Method bug found mid-run, worth keeping.** The first version computed sign
inversion as `cos(r1, −r4)` on raw spike counts. Counts are non-negative, so that
cosine can only land in [−1, 0] and was measuring whether two responses are
*parallel* — the opposite of the intent. Fixed by expressing every response as a
deviation from an all-groups-at-baseline reference. **+1 now means a passing
pair**; the protocol doc in flappy-haltere still says −1 and needs correcting.

---

## 2026-09-19 — Downstream trace (`haltere_downstream.py`)

**Question.** The pathway needs ~20 ms of drive before the motor pool fires.
Does haltere input converge onto progressively slower paths?

**Result: no — it diverges, and there are no slower cells to converge onto.**

| hop | new cells | cumulative | excitatory |
| --- | --- | --- | --- |
| 1 | 3,784 | 3,989 | **100%** |
| 2 | 60,400 | 64,389 | 53% |
| 3 | 98,051 | **162,440** | 56% |

By three synapses the signal has touched 97% of the 166,700 neurons. A single
2-cell cluster reaches 116,144 by hop 3. Every neuron in this model shares one
20 ms membrane constant, so cell identity cannot be what is slow. Hop 1 being
100% excitatory is a real structural fact and the expected one for cholinergic
afferents.

**What is actually slow: balanced convergence at the target.** The path to the
wing muscles is 1–2 synapses (1.8–3.6 ms), so delay explains nothing. But each
steering motor neuron is a *single cell* receiving 400–700 inputs of which
37–51% are inhibitory (power muscles: ~5,500 inputs, 33% inhibitory). A single
volley is cancelled; crossing threshold needs sustained excitation outpacing
balanced inhibition, which takes about one membrane time constant.

**Direct wiring is anti-predictive.** The five clusters reaching the motor pool
in one hop (SNpp14, 20, 25, 34, 35) are exactly the silent ones; both potent
clusters are two hops away. flappy-haltere had found direct wiring merely
unpredictive; it is worse than that.

---

## 2026-09-19 — Impulse response (`haltere_impulse.py`)

**Question.** Verify, rather than calculate, how much sub-wingbeat structure
survives to the motor pool. The prior claim was analytic: a 20 ms membrane
passes ~3.6% of a 218 Hz modulation.

**Result: a hard floor at ~4.4 wingbeats.**

| pulse | wingbeats | motor spikes | + 100 ms tail |
| --- | --- | --- | --- |
| 1, 2, 5, 10 ms | 0.2–2.2 | **0** | +0 |
| 20 ms | 4.4 | 3 | +182 |
| 100 ms | 21.8 | 56 | +239 |
| 500 ms | 109 | 653 | +241 |

Below ~20 ms of sustained drive the pool produces nothing at all — not a small
response, and not a delayed one. Stronger than the filtering argument it was run
to check: sub-wingbeat input does not produce an attenuated motor response, it
produces none. Once ignited the network rings >100 ms regardless of pulse length.

**Caveat noted at the time, and acted on.** This is the from-rest regime, where
threshold dominates. See the MTF entry above.

---

## 2026-09-19 — Device log and SNpp12 (Android `FlyMapActivity`)

Pulled 499 events from `design.antics.androsophila`. Whole session ran at
8.0 mV — below the recruitment threshold — so only SNpp12 did anything reliably
(24.2% of 62 touches; SNpp23 9.5%; every other cluster 0%).

**SNpp12 is one cell.** Stimulated alone, 500 ms from reset:

| cell | side | 8 mV | 10 mV | 12 mV | 14 mV |
| --- | --- | --- | --- | --- | --- |
| 801205 (idx 145211) | L | 3 | 108 | 9 | 13 |
| 946174 (idx 164845) | **R** | **611** | 848 | 893 | 861 |

The R cell carries essentially the whole cluster and is already supra-threshold
at 8 mV. The L cell is weak and non-monotonic, peaking at 10 mV — as
flappy-haltere's own targeted run had found.

**Its output is symmetric**, power_L 288 / power_R 290 at 8 mV, despite 2-hop
synapse counts favouring the right 138 to 89. Counted connectivity does not
predict which side fires, consistent with the divergence result.

**The device log's left-only pattern is an app artifact, not anatomy.** A clean
reset sim gives symmetric output and strong power-muscle firing; the device gave
`thorax_hz = 0` in all 62 SNpp12 rows and `wing_r_hz = 0` in all 499 rows of the
file. The app applies drive with decay (`decay ticks: 15`) against a live
never-reset brain, so it is a different protocol. This is the same reason
`inverse_data_device.py` re-simulates rather than using device readouts as
labels. No mid-decay contamination in this export (0 of 499 duplicate rows).

---

## 2026-09-18 — Does the fly fly? (`fly/render.py --hover`)

**No.** Net lift −0.023 body weights; `ellipsoid_fluid=True` gives +0.075 and no
wing fluid geoms gives −0.001. All zero. Peak in-beat force is ~4× body weight,
so the wings move plenty of air and a symmetric sine stroke cancels it over the
cycle. Cause is the bare-sine wing pattern — **inferred by elimination, not
measured**: the alternative (the measured figshare base pattern) has not been
run.

Lift measured with gravity zeroed, because a falling body sees an upward drag
indistinguishable from lift in `qfrc_passive`, tending to 1.0 at terminal
velocity. Averaged over whole wingbeats only; peak in-beat force exceeds the
mean by ~4×, so a partial beat biases the mean by more than the mean.

**Two bugs found on the way, either of which would have given a wrong answer.**
FlyGym ships the flybody fluid medium in centimetre units while the model is in
millimetres — 1000× too dense, denser than water. As shipped the fly sinks 2.8 mm
in 200 ms and looks nearly airborne. And the wingbeat was running at ~436 Hz
because the vendored WPG advances one 2e-4 s control step per call and was being
called every 1e-4 s physics step; only achieved wing amplitude reveals it.

---

## 2026-09-18 — Are the halteres wired up?

**No.** Bodies, joints, geoms and position actuators exist, but nothing commands
them: haltere qpos moves 3e-06 rad over 44 wingbeats, and the model has **zero
sensors** (`nsensor == 0`), so no Coriolis force is measured anywhere. The
connectome's 205 afferents are driven by an engineered scalar from thorax
angular velocity, which is identically zero while tethered.

Found a bug doing it: `_thorax_gyro` sliced `qvel[3:6]` as body angular velocity,
but `TetheredWorld` has no freejoint — those dofs are rostrum and haustellum
joints. The haltere afferents were being driven by the proboscis, and read zero
only because the mouthparts happened to be still.
