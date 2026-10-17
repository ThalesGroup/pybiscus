# Robust aggregation against malicious clients

The strategies of the `flowergeneric` plugin include aggregations meant to resist malicious
(byzantine) clients: `fedmedian` and `fedtrimmedavg` (coordinate-wise median and trimmed mean
[[Yin 2018]](#references); `beta`: fraction trimmed on each side), `krum` ([[Blanchard 2017]](#references);
`num_malicious_clients` f, `num_clients_to_keep` > 0 for Multi-Krum) and `bulyan`
([[El Mhamdi 2018]](#references); `num_malicious_clients` f; needs at least 4f + 3 clients, which
`server check` enforces on `min_fit_clients`: below, Flower fails in the middle of the aggregation).

Every table of this page is a measurement of ours, on Pybiscus, named after the campaign file that
produced it: none reproduces a paper's experiments. What separates them from a real deployment, and
how to extend them, is in [Limits of these measurements](#limits-of-these-measurements).

## The `robustness` setting

The short answer to "how do I protect a session": one line of the server configuration, or the
`robustness` choice of the session form (the manager then sets and locks it in the server's form):

```yaml
server_strategy:
  robustness: safeguard     # none (default) | safeguard
```

`safeguard` adds the `clipping` decorator in front of the pipeline when the configuration is
validated (`server check` and the server log say so): each update is clipped to 1.5 x the round's
median update norm, and those above 1.7 x are left out of the round. Measured below on cifar10, 7
clients, 3 seeds, iid and dirichlet shares:
- no cost without attacker (honest clients stayed below 1.5 x the median);
- attackers whose updates stand out (sign flip, scaling, ALIE from z 4) are rejected every round;
  what is lost is then their share of the data (nothing on iid shares, 6.5 points on dirichlet);
- **not stopped**: attackers that stay within the honest clients' range (ALIE at z 2: −5 points).
  No norm threshold separates them (see [Discreet attackers](#discreet-attackers-what-the-norm-cannot-see)).

A pipeline that already has a `clipping` decorator with other settings is refused with
`safeguard` (keep yours with `robustness: none`), as are the server-side DP decorators, which clip
already. Reference configuration: `configs/cifar10_cnn/distributed/without_ssl/server_safeguard.yml`.
The thresholds suit clients with comparable amounts of data and local steps: with a client far
larger than the others, check its `clip_ratio_<cid>` on a run without attacker first.

## Testing them: the `byzantine` client

`pybiscus-plugins/client/byzantine` is a client that trains honestly, then alters its update
delta = w_trained − w_global before sending it:

| `attack` | sent | |
|---|---|---|
| `sign_flip` (`scale`) | w_global − scale · delta | pulls the model the wrong way |
| `scale` (`scale`) | w_global + scale · delta | dominates the aggregate |
| `gaussian` (`stddev`) | w_global + noise | a faulty client |
| `none` | the honest update | with `num_examples_factor`, lies about its size only |
| `alie` (`colluders`, `num_clients`, `z`) | mean − z · deviation of the colluders' updates | discreet, see [ALIE](#a-discreet-colluding-attack-alie) |

`from_round` delays the attack, `seed` fixes the noise; the client reports a `byzantine` metric.
It is a test tool: it is declared in `launch/campaign/test-plugins-conf.yml` only, never in the
default manifest, so that it does not appear in a real session's forms. A client uses it through
`flower_client.alternate_client_class: {name: byzantine, config: {...}}`, with the test manifest
added: `PYBISCUS_PLUGIN_CONF_PATH=pybiscus-plugins/plugins-conf.yml:launch/campaign/test-plugins-conf.yml`.

The campaign tool ([Campaigns](campaigns.md)) takes the extra manifests (`plugin_manifests`) and
per-client settings for a variant (`client_overrides`, by client number):

```bash
uv run python launch/campaign/strategy_campaign.py launch/campaign/cifar10_robust.yml
```

A single run per cell cannot tell apart differences of a few points: two runs of the same
configuration gave 0.391 and 0.377. With `seeds: [1, 2, 3]` in the campaign file, every variant
runs once per seed (the server's and the clients' `seed`, the byzantine clients' noise) and a
second table gives the mean ± standard deviation over the seeds. The data shares stay those of the
partition's own seed, unless `seed_partitions: true` draws them again with each seed.
Most of that spread comes from the seed itself, shared by every variant: a variant with
`reference: <label of another variant>` also gets its difference to that variant at the last
round, seed by seed (mean ± standard deviation, and range), far steadier than the two means.
The same run repeated with the same seed still differs by up to 1 point after 5 rounds (rounding,
amplified by training): smaller differences mean nothing, even paired.

## Results (cifar10, 7 clients, iid shares, 3 local epochs, 5 rounds)

Test accuracy at round 5; attackers flip the sign of their update and scale it by 10.

| strategy | no attacker | 1 attacker | 2 attackers |
|---|---|---|---|
| FedAvg | 0.406 | 0.110 (collapsed) | 0.112 (collapsed) |
| FedMedian | 0.417 | 0.332 | 0.276 |
| FedTrimmedAvg, beta 0.2 | 0.354 | 0.380 | 0.099 (collapsed) |
| Krum, f 1 | 0.385 | 0.363 | 0.362 |
| Multi-Krum, f 1, keep 3 | 0.384 | 0.386 | 0.388 |
| Bulyan, f 1 | 0.391 | 0.364 | 0.387 |

- One attacker out of seven is enough to break FedAvg for the whole run.
- Beta 0.2 trims one client on each side out of seven: the second attacker stays in the mean.
- Krum, Multi-Krum and Bulyan resist two attackers although set for one: these attackers do not
  collude, and each lands far from the honest clients. Colluding attackers that stay close to
  them (smaller, coordinated changes) are the case these guarantees are about; not tested yet.
- Without attacker, the robust aggregations cost little on iid shares (single runs, differences of
  the order of the run-to-run noise).
- A client reporting 20 times its examples with an honest update barely changes FedAvg
  (0.373): the lie is harmful combined with a malicious update, not alone.

## Heterogeneous shares (dirichlet 0.5)

Same setting, each client dominated by a few classes (2 834 to 9 930 images): honest clients look
different from one another, and a robust aggregation may discard them as outliers
(`launch/campaign/cifar10_robust_dirichlet.yml`).

| strategy | no attacker | 1 attacker |
|---|---|---|
| FedAvg | 0.398 | 0.102 (collapsed) |
| FedMedian | 0.366 | 0.278 |
| FedTrimmedAvg, beta 0.2 | 0.355 | 0.285 |
| Krum, f 1 | 0.281 | 0.275 |
| Multi-Krum, f 1, keep 3 | 0.292 | 0.328 |
| Bulyan, f 1 | 0.333 | 0.348 |

- Without attacker, the robust aggregations now cost 3 to 12 points: Krum, which keeps a single
  client, loses the most (0.281 against 0.398), Bulyan the least of the Krum family.
- Against one attacker, the median and the trimmed mean hold less well than on iid shares (about
  0.28 against 0.33 to 0.38): the honest spread hides the attacker less clearly.
- Bulyan offers the best balance here. Single runs: differences of a few points are within the
  run-to-run noise.

## Norm clipping: FedAvg with bounded updates

Bounding the norm of each client's update before the mean ([[Sun 2019]](#references)) keeps
FedAvg's accuracy while limiting what one client can do. `serverdpfixed` with `noise_multiplier: 0` does exactly that (clipping of
`w_client - w_global` to `clipping_norm`, no noise); its log's `dp_clipped_fraction` shows how many
clients get clipped (`launch/campaign/cifar10_clipping_dirichlet.yml`, same dirichlet shares and
attacker as above):

| variant | no attacker | 1 attacker | clients clipped per round |
|---|---|---|---|
| FedAvg, no clipping | 0.398 | 0.102 | — |
| C = 0.5 | 0.264 | 0.170 | all: honest updates are bridled too |
| C = 1 | 0.373 | 0.287 | 86 % at first, then 29 % |
| C = 2 | 0.387 | 0.284 | the attacker only (1 of 7) |
| Bulyan, f 1 (for comparison) | 0.333 | 0.348 | — |

- Just above the size of the honest updates (C = 2 here), clipping costs one point without
  attacker — against 6.5 for Bulyan and 12 for Krum — and prevents FedAvg's collapse; under attack
  it stays below Bulyan. The size of an honest update can be read from `weight_drift` (strategy
  `fedprox` with `proximal_mu: 0`) or from `dp_clipped_fraction`.
- **Adaptive clipping** (`serverdpadaptive`, `noise_multiplier: 0`, `target_clipped_quantile: 0.5`)
  sets C by itself around the median of the update norms. Flower 1.27's
  `DifferentialPrivacyServerSideAdaptiveClipping` moved C away from its target: it counts the
  clipped updates in a rule written for the unclipped ones (`C *= exp(-lr * (clipped_fraction -
  target))`; in [[Andrew 2021]](#references), section 2.1, the indicator is 1 when the update is
  *not* clipped), and C decreased every round while 86 % of the updates were clipped. It also noised
  the aggregate with the next round's norm. Pybiscus uses a corrected subclass
  (`CorrectedAdaptiveClipping`): C now rises to about 1.1 and the clipped fraction stays around
  50 % (43 to 57 %).

| adaptive clipping, dirichlet | no attacker | 1 attacker |
|---|---|---|
| Flower's rule | 0.364 | 0.284 |
| corrected | 0.379 | 0.310 |

  Corrected, it needs no C to choose, costs about 2 points without attacker, and resists better
  than a fixed C under attack (single runs).

## The `clipping` decorator

A dedicated decorator (`pybiscus-plugins/strategydecorator/clipping`, family "Robustness") bounds
each client's update before the aggregation, whatever the strategy behind, without going through
DP (no epsilon, no `num_sampled_clients`, integer buffers left alone):

```yaml
server_strategy:
  pipeline:
  - name: clipping
    config:
      mode: median          # fixed (clipping_norm) | median (median_factor x the round's median norm)
      median_factor: 1.5
      reject_factor: 1.7    # optional: left out of the round above 1.7 x the median norm
      log_directions: false # optional: cosine similarities of the updates (see Discreet attackers)
```

- `median` sets C by itself every round, without lag, and a minority of clients cannot move the
  median.
- The update is measured against what each client was sent: listed after
  `personalizeclientsfitin` (enforced at check), it follows the personalized models. It cannot be
  combined with the server-side DP decorators, which clip already.
- Every round logs `clip_norm`, `clip_fraction`, the median and maximum update norms, the clipped
  clients, and for each client `clip_ratio_<cid>` = its update norm / the median: a client clipped
  round after round far above the median is a suspect.
- `log_directions: true` also logs, for each client, the cosine similarity of its update to the
  coordinate-wise median update and to its closest other client ("🧭" lines,
  `clip_cos_median_<cid>`, `clip_cos_closest_<cid>`). It changes nothing to the aggregation and
  costs a copy of every update: a diagnostic, to look at your own clients before choosing a defense.

Dirichlet shares, same attackers (`launch/campaign/cifar10_clipping_dirichlet.yml`; Bulyan from
`launch/campaign/cifar10_robust_dirichlet.yml`):

| variant | no attacker | 1 attacker | 2 attackers |
|---|---|---|---|
| FedAvg | 0.398 | 0.102 | — |
| clipping, median x 1.5 | 0.396 | 0.298 | 0.210 |
| clipping, median x 2 | 0.389 | 0.266 | 0.091 |
| clipping, median x 1.5, reject x 3 | 0.395 | 0.377 | 0.337 |
| Bulyan, f 1 | 0.333 | 0.348 | — |

- Without attacker, median x 1.5 costs nothing (one honest client clipped once in 5 rounds).
- The attackers were exactly the clipped clients every round (`clip_ratio` about 9.2 against 1.0).
- Clipping limits an attacker without removing it: its update, brought down to 1.5 times the
  median, still pulls the wrong way; with several attackers, clipping alone does not hold.
- **Rejection** (`reject_factor`) leaves out of the round's aggregation the clients above
  `reject_factor` x the median, and clips the others above `median_factor`: without attacker,
  nobody was rejected; with one or two, exactly the attackers, every round. It never goes below
  what the strategy needs to aggregate (Bulyan: 4f + 3 clients; `min_fit_clients` is how many to
  sample, not a quorum). A rejected client is back in the next round.
- Measured norm / median ratios: honest clients at most 1.5 (dirichlet shares from 2 800 to 9 900
  images), attackers 7.7 and above: a threshold of 3 leaves a wide margin. An honest client with
  far more data or local steps than the others makes larger updates: check its `clip_ratio`
  before lowering the threshold. Attacks designed to stay close to the honest updates (ALIE)
  pass under any such threshold; clipping still bounds them (next section).

**Choosing**: FedAvg + `clipping` (median x 1.5, reject x 1.7) resisted best here, at no cost
without attacker, and names the suspects. A threshold of 3 leaves a gap that discreet attackers
use (ALIE at z 4, below: −11 points instead of −6.5). Against attackers that stay below the
honest clients' norms (ALIE at z 2), no norm threshold helps, but Bulyan does not do better: it
costs 8 points on heterogeneous data before any attack.

## A discreet, colluding attack: ALIE

`attack: alie` ("A Little Is Enough", [[Baruch 2019]](#references)): the `colluders` attackers pool their
honest updates through `shared_dir` (one file per attacker and round, a `timeout` after which an
attacker alone sends its honest update), estimate coordinate-wise their mean and deviation, and all
send mean - z x deviation; z comes from the number of clients and of colluders
(`num_clients`), or is forced (`z`). For 7 clients and 2 colluders, z = 0.57
(`launch/campaign/cifar10_alie_dirichlet.yml`, dirichlet shares):

| defense | no attacker | 2 ALIE attackers |
|---|---|---|
| FedAvg | 0.398 | 0.391 |
| FedMedian | 0.366 | 0.370 |
| FedTrimmedAvg, beta 0.2 | 0.355 | 0.383 |
| Krum, f 1 | 0.281 | 0.297 |
| Multi-Krum, f 1, keep 3 | 0.292 | 0.333 |
| Bulyan, f 1 | 0.333 | 0.332 |
| clipping x 1.5, reject x 3 | 0.395 | 0.391 |

- The attack passes under the defenses: nothing clipped nor rejected, the attackers' norm ratio
  about 1 (their common update often is the median one).
- It does no measurable harm either: estimated from the colluders' two honest updates only, the
  mean is itself an honest average and the deviation small, so what they send is nearly honest.
- The paper's attackers do not know the honest updates either: they estimate them from the
  corrupted workers alone, but there are 12 of them among 51 workers (here 2 of 7), they attack the
  gradient of every step of a distributed SGD (here a model updated by 3 local epochs), with z = 1.
  It reports, on CIFAR10, accuracy drops of about 28 % without defense and 45 to 66 % with
  TrimmedMean, Bulyan and Krum. The worst case, attackers who know the honest updates, is measured
  below ([The omniscient attacker](#the-omniscient-attacker)).

### Sweeping z

The larger z, the further the colluders' common update from the honest mean: more harm, more
visible (`launch/campaign/cifar10_alie_z_sweep.yml`, 2 ALIE attackers of 7, dirichlet shares).
Test accuracy at round 5, mean ± standard deviation over 3 seeds:

| defense | no attacker | z 1 | z 2 | z 4 | z 8 |
|---|---|---|---|---|---|
| FedAvg | 0.402 ± 0.017 | 0.378 ± 0.015 | 0.348 ± 0.023 | 0.273 ± 0.028 | 0.146 ± 0.031 |
| clipping x 1.5, reject x 3 | 0.401 ± 0.019 | 0.378 ± 0.018 | 0.349 ± 0.023 | 0.296 ± 0.027 | 0.339 ± 0.018 |
| Bulyan, f 1 | 0.317 ± 0.040 | 0.303 ± 0.028 | 0.283 ± 0.049 | 0.292 ± 0.060 | 0.281 ± 0.055 |

The standard deviations mostly come from the seed itself (initial weights, batch order), shared by
every variant: the loss against the same seed without attacker is far steadier. For the clipping
defense: −2.3 points at z 1 (−2.0 to −2.5 over the seeds), −5.2 at z 2 (−4.8 to −5.8), −10.4 at
z 4 (−8.3 to −11.9), −6.2 at z 8 (−5.4 to −7.1).

Attackers' norm / median ratio under the clipping defense: about 1.0 (z 1), 1.2 (z 2, neither
clipped nor rejected), 1.8 (z 4, clipped every round), 4 (z 8, rejected every round).

- Undefended FedAvg loses 13 points at z 4 and collapses at z 8.
- Up to z 2 the clipping defense does nothing (same accuracy as FedAvg): the attack stays below
  its threshold and its bias passes whole, 2 to 5 points.
- Its worst case is z 4, not z 2: clipping bounds the attackers' norm but keeps their direction,
  and a ratio of 1.8 stays below the rejection threshold (3). At z 8 they are rejected: what is
  lost is then their share of the data (2 clients of 7).
- The clipping defense is still the most accurate, or level with Bulyan, at every z.
- Closing the gap means rejecting from a ratio of about 1.7, close to the honest clients' own
  ratios (up to 1.5 on these shares): the defense trades accuracy without attack against this
  margin.
- Bulyan loses 1 to 4 points at every z, from a start 8 points lower and with the largest
  run-to-run spread.

### Rejection threshold

`launch/campaign/cifar10_clipping_reject_alie.yml`: the clipping defense (median x 1.5) with three
rejection thresholds, without attacker and against 2 ALIE attackers of 7, dirichlet shares, 3
seeds. Test accuracy at round 5, and difference to the same threshold without attacker, seed by
seed:

| reject | no attacker | ALIE z 2 | ALIE z 4 |
|---|---|---|---|
| x 1.7 | 0.402 ± 0.018 | −5.4 ± 0.5 points | **−6.5 ± 0.5** (attackers rejected every round) |
| x 2 | 0.402 ± 0.015 | −5.4 ± 0.8 | −10.0 ± 2.5 (rejected in 1 seed of 3, clipped in the others) |
| x 3 | 0.402 ± 0.016 | −5.2 ± 0.4 | −11.0 ± 2.4 (clipped every round) |

- Without attacker no threshold rejected anybody: the largest honest ratio was 1.50 over the 15
  rounds of the 3 seeds, so x 1.7 costs nothing on these shares.
- At z 4 the attackers' ratio is close to 2: x 2 catches them by chance, x 1.7 every round. Once
  they are rejected, what is left (−6.5) is the loss of their 2 shares of 7, as at z 8.
- At z 2 the attackers' ratio stays between 1.0 and 1.25, inside the honest range: no norm
  threshold separates them, and their harm (−5.4) is about what rejecting them would cost anyway.
- x 1.7 is measured on these shares only. Clients whose data or local steps differ more than
  here make larger honest updates: check the `clip_ratio_<cid>` of a run without attacker first.

### On iid shares

`launch/campaign/cifar10_safeguard_iid.yml`: the same defense (median x 1.5, reject x 1.7) on iid
shares, 3 seeds, attackers flipping the sign of their update x 10. Test accuracy at round 5:

| | accuracy | difference, seed by seed |
|---|---|---|
| FedAvg, no attacker | 0.362 ± 0.030 | |
| clipping, no attacker | 0.363 ± 0.028 | +0.1 point vs FedAvg |
| clipping, 1 attacker | 0.363 ± 0.027 | −0.05 vs no attacker |
| clipping, 2 attackers | 0.363 ± 0.025 | −0.02 vs no attacker |

Honest clients stay below 1.11 x the median (1.50 on dirichlet shares): nobody honest was clipped
or rejected; the attackers (about 10 x) were rejected every round, in every seed. Leaving 2
clients of 7 out costs nothing here, as their data is much like the others' (−6.5 points on
dirichlet shares).

### The omniscient attacker

The worst case of ALIE: the attackers know the honest updates of the round. Only the server sees
them all, so the attack is simulated there: the `omniscientalie` strategy decorator (test manifest
only) replaces the updates of the clients flagged byzantine (`byzantine`, `attack: none`: they
train honestly) by mean − z · std of the honest updates. It must wrap the defenses (listed after
`clipping` and the server-side DP decorators, enforced at check), so that they see the forged
updates. `z` unset takes the paper's value for the round's numbers of clients and attackers;
`from_round` delays the attack.

`launch/campaign/cifar10_alie_omniscient.yml`: 7 clients of which 2 attackers, dirichlet shares,
5 rounds of 3 local epochs; test accuracy at round 5, mean over 3 seeds, and the difference to the
same defense without attacker, paired by seed (mean ± std, min to max):

| defense | no attacker | omniscient, z 0.57 (paper) | Δ | omniscient, z 2 | Δ |
|---|---|---|---|---|---|
| FedAvg | 0.401 | 0.326 | −0.075 ± 0.007 | 0.292 | −0.109 ± 0.005 |
| FedMedian | 0.354 | 0.266 | −0.088 ± 0.007 | 0.243 | −0.111 ± 0.007 |
| FedTrimmedAvg, beta 0.2 | 0.366 | 0.292 | −0.075 ± 0.005 | 0.248 | −0.119 ± 0.012 |
| Krum, f 1 | 0.276 | 0.272 | −0.005 ± 0.009 | 0.301 | +0.025 ± 0.024 |
| Bulyan, f 1 | 0.321 | 0.266 | −0.055 ± 0.048 (−0.100 to −0.004) | 0.277 | −0.045 ± 0.075 (−0.121 to +0.030) |
| clipping x 1.5, reject x 1.7 | 0.401 | 0.327 | −0.074 ± 0.005 | 0.291 | −0.110 ± 0.005 |

- Knowing the honest updates turns a harmless attack (client-side, above) into a steady one:
  7.5 points lost by FedAvg at the paper's z, 11 at z 2, with little spread between seeds.
- The median and the trimmed mean do no better than FedAvg: the forged update sits inside the
  honest range on every coordinate, which is what they keep.
- Clipping sees nothing: no client rejected in any round, clipped in 2 rounds of 30, and its
  results match FedAvg's.
- Krum, f 1, picks the forged update every round at z 0.57: the two identical copies are at
  distance 0 from each other, which lowers their score. It costs nearly nothing, though: that update
  is built from the mean of the 5 honest ones, while Krum alone keeps a single client's update. At
  z 2, the forged copies are too far away and Krum never picks them; its gain is within the spread
  of the seeds. These picks were checked on 2 seeds by a temporary log of Krum's scores (DEVLOG).
  Krum stays the weakest defense before any attack (−12 points against FedAvg).
- Bulyan's results spread too much over 3 seeds to conclude (one seed below 0.25 without attacker).
- These are not the paper's results: 2 attackers of 7 and federated rounds, against 12 of 51 and
  every gradient step there ([Limits](#limits-of-these-measurements)).

## Discreet attackers: what the norm cannot see

### The limit

The `safeguard` defense judges updates by their norm. ALIE at z ≤ 2 keeps the attackers' norms
within the honest clients' range (1.0 to 1.25 x the median), so no norm threshold separates them:
on dirichlet shares they cost 2.5 points at z 1 and 5.7 at z 2, paired by seed. From z 4 they
stand out and are rejected.

### Direction to the median does not help

`launch/campaign/cifar10_directions_alie.yml` logs the directions (`log_directions`) on dirichlet
shares, 7 clients, 2 seeds. Ranges over all rounds:

| case | honest → median | honest → closest | attackers → median | attackers → closest |
|---|---|---|---|---|
| no attacker | 0.05 … 0.87 | 0.14 … 0.82 | | |
| ALIE z 1 | 0.01 … 0.82 | 0.14 … 0.81 | 0.69 … 0.84 | 1.000 |
| ALIE z 2 | −0.02 … 0.80 | 0.14 … 0.80 | 0.60 … 0.70 | 1.000 |
| ALIE z 4 | 0.01 … 0.80 | 0.14 … 0.81 | 0.47 … 0.62 | 1.000 |
| sign flip x 10 | 0.20 … 0.66 | 0.15 … 0.81 | −0.44 … 0.21 | 0.25 … 0.70 |

ALIE aims at the honest mean: its updates are more aligned with the median than many honest
ones, which heterogeneous data spreads in every direction. The direction to the median only
singles out the sign flippers, which their norm already gives away.

### The signal there is: the attackers' likeness

The colluders send the same update (similarity 1.000), while two honest clients never exceeded
0.82. Two ways to use it, neither implemented yet:

- **Rejecting near-duplicates** (option A): leave out of the round the clients whose closest
  similarity exceeds about 0.95, as `reject_factor` does for norms. Cheap, and it stops naive
  colluders at every z. To check first: the honest clients' closest similarity on iid shares, where
  their updates look more alike (measured below: it rules out such a threshold). Its weakness:
  colluders that each add their own noise blur their likeness, at the price of part of their effect.
- **Defenses from the literature** (option C):
  - *FoolsGold* lowers, round after round, the weight of the clients that keep looking like each
    other. A lasting version of the above, harder to blur with one-off noise, but it may also
    weigh down honest clients whose data are alike.
  - *FLTrust* compares each update with one the server computes itself on a small trusted dataset
    (the `test` section could provide it) and weighs it by their similarity. It does not rely on
    the attackers' likeness, but the trusted data must resemble the clients'.

### On iid shares, honest clients look alike too

`launch/campaign/cifar10_directions_iid.yml`: the same defense (FedAvg + clipping, median x 1.5,
reject x 1.7, `log_directions`) on iid shares, 7 clients, 3 seeds, without attacker, against 2
client-side ALIE colluders (z 2) and against 2 omniscient ALIE attackers (the paper's z and z 2).
Each honest client's similarity to its closest other client, over all rounds and seeds:

| case | median | 95th percentile | max | honest above 0.95 | attackers |
|---|---|---|---|---|---|
| no attacker | 0.941 | 0.985 | 0.988 | 44 of 105 | |
| client-side ALIE z 2 | 0.944 | 0.985 | 0.988 | 32 of 75 | 1.000 |
| omniscient, paper z (0.57) | 0.964 | 0.990 | 0.993 | 48 of 75 | 1.000 |
| omniscient, z 2 | 0.943 | 0.986 | 0.988 | 33 of 75 | 1.000 |

- The honest clients' closest similarity depends on the round (median 0.93 at round 1, 0.98 at
  round 2, 0.89 at round 5): a threshold of 0.95 would reject 4 honest clients in 10.
- Only the identical copies stand apart (1.000 against at most 0.993): a threshold close to 1
  would catch colluders sending the same update, and no colluder adding the smallest noise of its own.
- Rejecting near-duplicates by a fixed threshold is therefore not implemented.

The attack's harm on iid shares, test accuracy at round 5 paired by seed against the run without
attacker (0.363): client-side ALIE z 2 −0.7 ± 0.7 points, omniscient at the paper's z −0.2 ± 0.2,
omniscient at z 2 −1.1 ± 0.7. Nothing was clipped nor rejected. On iid shares, every honest
update already points close to the mean, so a forged update close to it changes little: the
attack hurts where the data are heterogeneous (−7.5 to −11 points on dirichlet shares, [The
omniscient attacker](#the-omniscient-attacker)).

### Is detecting them worth it?

Little, in these measurements. On dirichlet shares, leaving 2 clients of 7 out costs 6.6 points
(their data are lost), about as much as ALIE at z 2 harms (5.7): even a perfect detector would
gain little against the client-side attack, more against the omniscient one (11 points at z 2).
On iid shares, leaving them out costs nothing (see [On iid shares](#on-iid-shares)), but the attack
does almost no harm there either (about 1 point).

Before choosing, look at your own clients with `log_directions: true` on a run without attacker:
how far apart their directions are, and how close the closest pair gets.

## Limits of these measurements

The campaigns compare defenses under the same conditions; they do not say how a defense behaves in
a given deployment, nor do they reproduce the papers' figures. What they leave out:

- **Few participants**: 7 clients, every one in every round, on one machine (each client is a
  process holding the model and its data, which bounds their number on one machine). Real
  federations have tens to thousands of clients, sampled each round. The robust aggregations'
  guarantees, and an attacker's estimate of the honest updates, depend on that number: the ALIE
  paper has 12 attackers among 51 workers, here 2 among 7.
- **Federated rounds, not gradient steps**: each update is a model trained for 3 local epochs,
  where the papers (Krum, Bulyan, ALIE) attack and defend the gradient of every step of a
  distributed SGD. An update is larger and noisier than a gradient, so the thresholds measured
  here (1.5, 1.7 x the median) do not carry over.
- **Short, unfinished training**: 5 rounds, about 0.40 test accuracy on 2 000 test images. A defense
  may cost more, or less, once the model has converged.
- **One dataset, two kinds of shares**: cifar10, iid or dirichlet 0.5, every client with the same
  number of local epochs. Clients whose amounts of data or local steps differ make honest updates
  of very different sizes, which a norm threshold then confuses with attackers.
- **Simple attackers**: always the same clients, attacking every round, the number of attackers
  given to Krum and Bulyan. No attacker adapts to the defense, changes over time, poisons its labels
  or plants a backdoor; the client-side ALIE estimates the honest updates from 2 colluders only.
- **Few repetitions**: 3 seeds; differences under about 1 point mean nothing, even paired (see
  [Testing them](#testing-them-the-byzantine-client)).

### Extending a campaign

Every limit above is a key of the campaign file ([campaigns.md](campaigns.md)):

| to test | change | cost |
|---|---|---|
| more participants | `clients: 20`, the attackers in `client_overrides` (e.g. 5 of them), `num_clients: 20` and `colluders: 5` for the client-side ALIE | memory and time grow with the clients; here, 7 clients took about 1 min per run: on a larger machine, or with `server_data.test.max_samples` lowered and a smaller model (`configs/mnist_cnn/`) |
| the ALIE paper's setting, closer | client-side `attack: alie` (not omniscient), about 24 % of colluders (5 of 20), `z: 1.0` | as above; the attack still targets federated updates, not gradients |
| converged models | `rounds: 20` or more | proportional to the rounds |
| more repetitions | `seeds: [1, 2, 3, 4, 5]`; `seed_partitions: true` to draw the shares again with each seed | proportional to the seeds |
| other heterogeneity | `client_data.train.partition`: `alpha: 0.1` (stronger) or `1.0`, `scheme: shards` | none |
| other data and models | `server_config` and `client_config` of another use case | depends on the model |
| an attack starting late | `from_round` of the byzantine client or of `omniscientalie` | none |
| the honest clients' own spread | a run without attacker, `log_directions: true` on the `clipping` decorator, then `clip_ratio_<cid>` and the cosines | one run |

Before a large campaign, run one variant with one seed (`--only`, `seeds: [1]`) to measure the time
per run, and keep it away from a live session.

## References

- [Baruch 2019] M. Baruch, G. Baruch, Y. Goldberg. *A Little Is Enough: Circumventing Defenses For
  Distributed Learning*. NeurIPS 2019. [arXiv:1902.06156](https://arxiv.org/abs/1902.06156) — the
  ALIE attack (`byzantine`, `attack: alie`; `omniscientalie` is its worst-case variant, not the
  paper's threat model).
- [Blanchard 2017] P. Blanchard, E. M. El Mhamdi, R. Guerraoui, J. Stainer. *Machine Learning with
  Adversaries: Byzantine Tolerant Gradient Descent*. NeurIPS 2017.
  [Proceedings](https://papers.nips.cc/paper/2017/hash/f4b9ec30ad9f68f89b29639786cb62ef-Abstract.html)
  — Krum and Multi-Krum (`krum`).
- [El Mhamdi 2018] E. M. El Mhamdi, R. Guerraoui, S. Rouault. *The Hidden Vulnerability of
  Distributed Learning in Byzantium*. ICML 2018, PMLR 80. [arXiv:1802.07927](https://arxiv.org/abs/1802.07927)
  — Bulyan and its n ≥ 4f + 3 (`bulyan`).
- [Yin 2018] D. Yin, Y. Chen, K. Ramchandran, P. Bartlett. *Byzantine-Robust Distributed Learning:
  Towards Optimal Statistical Rates*. ICML 2018. [arXiv:1803.01498](https://arxiv.org/abs/1803.01498)
  — coordinate-wise median and trimmed mean (`fedmedian`, `fedtrimmedavg`).
- [Sun 2019] Z. Sun, P. Kairouz, A. T. Suresh, H. B. McMahan. *Can You Really Backdoor Federated
  Learning?* FL workshop at NeurIPS 2019. [arXiv:1911.07963](https://arxiv.org/abs/1911.07963) —
  norm clipping of the updates as a defense (`clipping`).
- [Andrew 2021] G. Andrew, O. Thakkar, H. B. McMahan, S. Ramaswamy. *Differentially Private
  Learning with Adaptive Clipping*. NeurIPS 2021. [arXiv:1905.03871](https://arxiv.org/abs/1905.03871)
  — the adaptive clipping norm (`serverdpadaptive`, corrected rule).

The strategies themselves are Flower's (`flwr.server.strategy`); the server-side DP and its
references are described in [configuration.md](configuration.md#server-side-differential-privacy).
