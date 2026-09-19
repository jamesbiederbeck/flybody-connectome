# Experiment log

Newest first. Each entry: what was asked, what was run, what came back, and what
it changed. Negative results and corrections to earlier entries stay in — an
entry is never edited to look better in hindsight, it gets a follow-up.

Conventions used throughout: a fresh `NativeBrain` (or a verified state reset)
per condition, because both brain and physics state carry; every claim labelled
measured or inferred; and a stated control for anything that could be produced
by the setup rather than the thing being measured.

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
