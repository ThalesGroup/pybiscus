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
| `label_flip` (`num_classes`) | the update trained on labels l → num_classes − 1 − l | data poisoning: an honest norm, the wrong direction, see [Label flipping](#label-flipping-poisoned-data) |

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
      size_scaling: sqrt_examples # default: norms compared at the median share size; none: as they are
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
- `size_scaling: sqrt_examples` (the default) divides each norm by the square root of the client's number of
  examples over the median one before comparing it: with a fixed number of local epochs, a client
  with a large share makes more steps and larger updates, and is otherwise taken for an outlier
  ([measured at 20 clients](#clipping-at-20-clients-the-size-of-the-shares)). It trusts the
  number of examples each client reports, as FedAvg's weights do: a client that inflates it by k
  gains √k of norm margin, besides k times its weight. The measurements of this page made before
  it (all but that section) are with `size_scaling: none`, written in their campaign files.
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
without attacker, and names the suspects. Keep `size_scaling: sqrt_examples`, the default, on
shares of uneven sizes: at 20 clients it keeps the largest honest client, which `none` rejects
([measured](#clipping-at-20-clients-the-size-of-the-shares)). A threshold of 3 leaves a gap that discreet attackers
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

### At the paper's proportion: 5 attackers of 20

`launch/campaign/cifar10_alie_20clients.yml`: 20 clients of which 5 attackers (about the paper's
12 of 51), its z 1, dirichlet 0.5 shares, 10 rounds of 3 local epochs, every defense set for 5
attackers (Bulyan f 4: it needs 4 f + 3 clients). Each defense without attacker, against 5
client-side colluders (`attack: alie`, `colluders: 5`) and against the omniscient attacker at the
same z; test accuracy at round 10, mean over 3 seeds, and the difference to the same defense without
attacker, paired by seed (mean ± std, min to max):

| defense | no attacker | 5 colluders, z 1 | Δ | omniscient, z 1 | Δ |
|---|---|---|---|---|---|
| FedAvg | 0.364 | 0.355 | −0.009 ± 0.002 | 0.349 | −0.015 ± 0.002 |
| FedMedian | 0.302 | 0.280 | −0.023 ± 0.001 | 0.277 | −0.026 ± 0.011 |
| FedTrimmedAvg, beta 0.25 | 0.307 | 0.290 | −0.017 ± 0.009 | 0.288 | −0.019 ± 0.019 (−0.038 to +0.001) |
| Krum, f 5 | 0.147 | 0.162 | +0.015 ± 0.043 | 0.249 | +0.102 ± 0.023 |
| Bulyan, f 4 | 0.256 | 0.216 | −0.040 ± 0.006 | 0.197 | −0.059 ± 0.031 (−0.089 to −0.028) |
| clipping x 1.5, reject x 1.7 | 0.343 | 0.326 | −0.017 ± 0.004 | 0.321 | −0.022 ± 0.004 |

- With 5 colluders, the client-side attack does measurable harm, steady over the seeds: their
  estimate of the honest distribution, from 5 updates, comes close to the omniscient attacker's
  (within a point everywhere but Bulyan). At 2 of 7 it did nothing.
- The harm is smaller than at 7 clients (omniscient: 7.5 points lost by FedAvg at the paper's z):
  each attacker weighs 1/20 of the mean, and z 1 is a small deviation.
- The defenses that select or sort the updates suffer most, as in the paper, and FedAvg least:
  Bulyan loses 4 to 6 points, from an accuracy already 11 points below FedAvg's; the median and the
  trimmed mean 2 to 2.5. Under attack, every defense ends below FedAvg under the same attack.
- Krum, f 5, does not learn on these shares (0.147 without attacker, chance with one seed): it keeps
  a single update of 20, one client's skewed share. The omniscient attacker "helps" it by 10 points:
  the 5 identical forged copies get the best score, and that update is built from the mean of the 15
  honest ones. Its gain is no defense.
- Clipping never clips nor rejects an attacker. It rejects one honest client (cid 15) in 7 to 10
  rounds of 10, with or without attacker: the client with the largest share, not a skewed one
  (next section).
- 20 clients take about 1.2 GB of memory each (24 GB and 4.6 GB of swap here) and 2.5 minutes per
  run of 10 rounds; 54 runs took 3 h 10, including the machine's pauses.

### Clipping at 20 clients: the size of the shares

The rejected client, cid 15, holds 5 281 training images, 2.44 times the median share, with
ordinary classes (7 above 2 %, the main one at 29 %). With 3 local epochs, the number of steps,
and the update norm, grow with the share: over the 20 clients, the correlation between the share
size and the mean `clip_ratio` is 0.91 to 0.95 (3 seeds). Replayed on the logged ratios, dividing
the norm by the number of examples flags the small clients instead (12 to 17 ratios above 1.7 per
run); by its square root, no ratio goes above 1.6. Hence `size_scaling: sqrt_examples`.

`launch/campaign/cifar10_clipping_size_20clients.yml`: same setting (dirichlet 0.5, 20 clients,
10 rounds of 3 epochs), clipping x 1.5, reject x 1.7 with and without the scaling; test accuracy at
round 10, mean over 3 seeds, difference paired by seed (no attacker: to FedAvg; attacked: to the
same defense without attacker):

| variant | no attacker | Δ vs FedAvg | 5 sign flippers x 10 | Δ | 5 ALIE colluders, z 1 | Δ |
|---|---|---|---|---|---|---|
| FedAvg | 0.364 | | | | | |
| clipping | 0.343 | −0.021 ± 0.007 | 0.344 | +0.001 ± 0.010 | | |
| clipping, `sqrt_examples` | 0.364 | −0.000 ± 0.001 | 0.361 | −0.003 ± 0.002 | 0.355 | −0.009 ± 0.001 |

- Without the scaling, cid 15 is rejected in 7 rounds of 10 on every seed and clipped in the
  others; its loss is the whole cost of clipping without attacker (2.1 points). Under sign flippers,
  it is rejected with them in 11 rounds of 30.
- With the scaling, nobody is rejected without attacker and a single honest client is clipped once
  in 30 rounds: the result matches FedAvg's within 0.1 point on every seed. The 5 sign flippers are
  rejected in every round of the 3 seeds, alone, and cost 0.3 point.
- Against ALIE z 1, the loss (0.9 point) is FedAvg's under the same attack: the forged update is not
  rejected. Attacker cid 0 (697 images, the smallest share) is clipped in 2 to 4 rounds: its forged
  update has the size of the others', which is large for its share (one honest client clipped once
  besides, in 30 rounds).

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
    weigh down honest clients whose data are alike. Implemented and measured below
    ([FoolsGold](#foolsgold-clients-that-look-alike)).
  - *FLTrust* compares each update with one the server computes itself on a small trusted dataset
    and weighs it by their similarity. It does not rely on the attackers' likeness, but the trusted
    data must resemble the clients'. Implemented and measured below ([FLTrust](#fltrust-a-direction-the-server-trusts)).

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

## FLTrust: a direction the server trusts

The `fltrust` strategy decorator ([[Cao 2021]](#references)) trains, every round, the global model on
a few trusted examples the server holds (the data section `trusted`, see
[configuration.md](configuration.md#data)), and judges each client by the direction of its update:

- its weight is the cosine similarity of its update to the server's, 0 when negative (left out of
  the round);
- its update is scaled to a common norm, so that no client weighs by its norm (`normalize_to`);
- FedAvg averages the scaled updates with these weights (passed as `num_examples`): `fltrust`
  works over `fedavg` and `fedprox` only, and cannot be combined with `clipping` (which `robustness:
  safeguard` adds) nor the server-side DP decorators, all enforced at check.

```yaml
server_strategy:
  strategy: {name: fedavg, config: {}}
  pipeline:
    - name: fltrust
      config: {}               # normalize_to: median, server_steps: clients
data:
  config:
    trusted:
      max_samples: 500         # the default; drawn at random from the train split (dir), seed 0
```

Every round logs each client's trust score ("🛡️" lines, `fltrust_score_<cid>`), the server's
number of steps and update norm, and how many clients were left out.

Two choices differ from the paper, because its clients run one local iteration each, as the
server, while Pybiscus clients run local epochs:

- `server_steps: clients` (default): the server runs as many optimizer steps as the median client
  (its number of examples x the local epochs / the trusted batch size), going through the trusted
  examples again and again. With the clients' number of epochs instead (`server_steps: epochs`),
  100 examples gave 12 steps against 650, a direction too short to say anything: the model did not
  learn at all on a trial seed.
- `normalize_to: median` (default): the updates are scaled to the median client norm. The paper's
  choice, the server update's norm (`normalize_to: server`), cost 18 points without attacker below:
  overfitting its 100 examples, the server's update is about twice as long as the clients', and
  every update was stretched to it.

`launch/campaign/cifar10_fltrust.yml`: dirichlet shares, 7 clients, 3 local epochs, 5 rounds, 100
trusted examples, 3 seeds; test accuracy at round 5, and the difference to the same defense without
attacker paired by seed:

| variant | no attacker | omniscient ALIE, z 0.57 | omniscient ALIE, z 2 | 2 sign flippers x 10 |
|---|---|---|---|---|
| FedAvg (no defense) | 0.404 | 0.326 ¹ | 0.292 ¹ | 0.102 with 1 ² |
| FLTrust, `normalize_to: median` | 0.372 (−3.2 vs FedAvg) | 0.313 (−5.8) | 0.319 (−5.3) | 0.327 (−4.5) |
| FLTrust, `normalize_to: server` | 0.219 (−18.5 vs FedAvg) | 0.227 (+0.8) | 0.243 (+2.4) | 0.241 (+2.2) |
| clipping x 1.5, reject x 1.7 (`safeguard`) | 0.401 ¹ | 0.327 ¹ | 0.291 ¹ | 0.337 with reject x 3 ² |

¹ [The omniscient attacker](#the-omniscient-attacker), same setup; ² the clipping campaign
([The `clipping` decorator](#the-clipping-decorator)), same setup.

Trust scores over all rounds and seeds (`normalize_to: median`; the attackers are clients 0 and 1):

| case | honest: mean score, left out | attackers: mean score, left out |
|---|---|---|
| no attacker | 0.27, 2 of 105 | |
| omniscient ALIE, z 0.57 | 0.26, 2 of 75 | 0.33, 0 of 30 |
| omniscient ALIE, z 2 | 0.25, 3 of 75 | 0.07, 2 of 30 |
| sign flip x 10 | 0.24, 3 of 75 | 0, 30 of 30 |

- The sign flippers were left out of every round: FLTrust stops them without knowing their number,
  where FedAvg collapses. The `safeguard` defense does it too, at no cost without attacker.
- Omniscient ALIE at z 2 keeps the attackers' weight at a quarter of the honest clients' (0.07
  against 0.25): FLTrust ends 2.7 points above FedAvg and `safeguard` (0.319 against 0.292 and
  0.291); Krum, which never picks the forged update at z 2, ends at 0.301 but costs 12 points
  without attacker.
- At the paper's z (0.57), the forged update is closer to the server's direction than the honest
  ones (0.33 against 0.26): FLTrust trusts the attackers more and does no better than FedAvg.
- Its cost without attacker, 3.2 points, comes from the weights: the honest clients' scores are low
  (about 0.27) and uneven, 100 examples giving a rough direction on heterogeneous data.

**Choosing**: `safeguard` stays the default advice: no cost without attacker, and it stops the
attackers that stand out by their norm. FLTrust is worth its cost only when the server holds data
like the clients' and discreet attackers are expected; even then, an attacker that knows the honest
updates and stays close to their mean passes it. Not measured: more clients.

### How many trusted examples

`launch/campaign/cifar10_fltrust_trusted_size.yml`: the same setup, `trusted.max_samples` 100 (the
paper's), 500 and 2000 (a variant's `server_data`), without attacker (difference to FedAvg, 0.401)
and against 2 label flippers ([Label flipping](#label-flipping-poisoned-data); difference to the same
size without attacker), 3 seeds:

| trusted examples | no attacker | Δ vs FedAvg | 2 label flippers | Δ |
|---|---|---|---|---|
| 100 | 0.370 | −0.030 ± 0.012 | 0.309 | −0.061 ± 0.009 |
| 500 | 0.379 | −0.022 ± 0.003 | 0.330 | −0.048 ± 0.012 |
| 2000 | 0.375 | −0.026 ± 0.005 | 0.323 | −0.052 ± 0.006 |

- From 100 to 500, the honest clients' mean trust score, without attacker, rises from 0.22–0.31 to
  0.35–0.52 over rounds 2 to 5: the server's direction is steadier. Under attack, FLTrust ends 4.4 points above FedAvg
  (0.330 against 0.286), against 2.3 with 100.
- Beyond, nothing more: 2000 does no better than 500 (the differences are within the seeds' spread).
- The cost without attacker shrinks a little but stays, about 2 points: the trust weights, uneven
  from one honest client to another on heterogeneous data, keep away from FedAvg's weighting by
  number of examples.

Hence the default of 500 (`trusted.max_samples`), and not the paper's 100; the campaigns above set
100 explicitly.

### FLTrust on iid shares

`launch/campaign/cifar10_fltrust_iid.yml`: iid shares, 7 clients, 500 trusted examples (the
default), 3 seeds; test accuracy at round 5, and the difference to the same defense without attacker
paired by seed (FLTrust without attacker: to FedAvg):

| defense | no attacker | 2 label flippers | omniscient ALIE, z 2 | 2 sign flippers x 10 |
|---|---|---|---|---|
| FedAvg | 0.362 | 0.341 (−2.1 ± 0.5) | 0.355 (−0.8 ± 0.3) | (collapses) |
| FLTrust | 0.364 (+0.2 ± 0.1 vs FedAvg) | 0.354 (−1.0 ± 0.4) | 0.354 (−1.0 ± 0.5) | 0.365 (+0.1 ± 0.6) |

- Where the trusted examples look like every client's data, FLTrust costs nothing: the honest
  clients' trust scores are high and even (0.70 on average, none left out), against 0.27 to 0.5 on
  dirichlet shares.
- The sign flippers were left out of every round; the label flippers kept half the honest clients'
  weight (0.35 against 0.70), which halves their harm.
- Omniscient ALIE passes (0.63 against 0.70): it does almost no harm on iid shares anyway (see
  [On iid shares, honest clients look alike too](#on-iid-shares-honest-clients-look-alike-too)).
- The attacks themselves harm little here: 2 points for label flipping, under 1 for ALIE. FLTrust's
  case is heterogeneous data, where it costs 2 to 3 points.

### FLTrust at 20 clients

`launch/campaign/cifar10_fltrust_20clients.yml`: dirichlet shares, 20 clients of which 5 attackers,
3 local epochs, 10 rounds, 500 trusted examples and `normalize_to: median` (the defaults), 3 seeds;
the same setting as [ALIE at 5 attackers of 20](#at-the-papers-proportion-5-attackers-of-20). Test
accuracy at round 10, and the difference to the same defense without attacker paired by seed
(FLTrust without attacker: to FedAvg):

| defense | no attacker | 5 ALIE colluders, z 1 | omniscient ALIE, z 1 | 5 sign flippers x 10 |
|---|---|---|---|---|
| FedAvg | 0.364 | 0.355 (−0.9 ± 0.3) | 0.350 (−1.4 ± 0.2) | 0.099 (−26.6 ± 1.6, chance) |
| FLTrust | 0.329 (−3.5 ± 0.8 vs FedAvg) | 0.322 (−0.7 ± 0.9) | 0.316 (−1.3 ± 0.8) | 0.326 (−0.2 ± 0.7) |

- FLTrust costs 3.5 points without attacker, on every seed: with a twentieth of uneven data each,
  the honest clients' trust scores spread from 0.08 to 0.52 (about 0.3 in the middle), so a few
  honest clients count four to six times less than others.
- The sign flippers, which bring FedAvg down to chance (10 classes), are left out of every round
  (score 0) and do no harm: this is what FLTrust buys.
- ALIE at z 1 passes: its updates score 0.17 to 0.24, inside the honest range. It harms FLTrust no
  more and no less than FedAvg, about one point, which is within the noise of three seeds.
- At 20 clients FLTrust is worth its cost only against attackers whose direction stands out (sign
  flipping, scaled updates); against ALIE, which harms little at z 1, it adds a cost and no defense.

## Label flipping: poisoned data

`attack: label_flip`: the attacker trains on its own data with every label l replaced by
num_classes − 1 − l (the LF attack of [[Cao 2021]](#references)) and sends that update unchanged. It
touches no code nor weight: a client with corrupted labels does the same. Its update has an
honest norm and the wrong direction.

`launch/campaign/cifar10_label_flip.yml`: 2 label flippers of 7, dirichlet shares, 3 local epochs,
5 rounds, 3 seeds; test accuracy at round 5, and the difference to the same defense without
attacker paired by seed (mean ± std):

| defense | no attacker | 2 label flippers | Δ |
|---|---|---|---|
| FedAvg | 0.402 | 0.286 | −0.116 ± 0.011 |
| FedMedian | 0.354 | 0.277 | −0.077 ± 0.012 |
| Krum, f 1 | 0.275 | 0.290 | +0.015 ± 0.015 |
| Bulyan, f 1 | 0.305 | 0.272 | −0.034 ± 0.018 |
| `safeguard` (clipping x 1.5, reject x 1.7) | 0.401 | 0.284 | −0.116 ± 0.008 |
| FLTrust (`normalize_to: median`) | 0.372 | 0.309 | −0.063 ± 0.007 |

- The norm sees nothing: `safeguard` clipped and rejected no client in any round, and loses as
  much as FedAvg (11.6 points).
- FLTrust ends highest under attack (0.309, 2.3 points above FedAvg and `safeguard`), for 3 points
  lost without attacker. It learns to distrust the flippers as the model learns: their mean trust
  score, 0.32 against 0.26 for the honest clients at round 1, falls to 0.09 against 0.20 at round
  5. It never left them out (no score at 0).
- The median halves the harm but starts 5 points lower; Krum keeps one honest update every round
  and stays where it was, 13 points below FedAvg without attacker.

**Choosing**, against data poisoning: no defense measured here does better than FedAvg without
attacker and holds under attack. If poisoned data is the threat and the server holds data like the
clients', FLTrust is the best trade-off measured: −3 points without attacker, +2.3 under attack,
and its trust scores name the suspects.

## FoolsGold: clients that look alike

The `foolsgold` strategy decorator ([[Fung 2020]](#references), Algorithm 1) keeps, for each client,
the sum of its updates so far (its history), and weighs it down when that history looks like
another client's:

- its weight is 1 − its largest cosine similarity to another client's history, lowered less when
  that other client looks even more like a sybil (pardoning), rescaled so that the largest weight
  is 1, then passed through a logit of confidence `kappa` (1, the paper's) and clipped to [0, 1]:
  a client at 0 is left out of the round;
- FedAvg averages the updates with these weights (passed as `num_examples`), where the paper adds
  the weighted gradients of a federated SGD: `foolsgold` works over `fedavg` and `fedprox` only,
  outside `clipping` when both are used, and not with `fltrust` (both set the weights);
- every weight counts in the similarity, not the paper's output-layer feature importance.

Every round logs each client's weight ("🪙" lines, `foolsgold_weight_<cid>`) and how many were left
out.

`launch/campaign/cifar10_foolsgold.yml` (dirichlet shares) and `cifar10_foolsgold_iid.yml` (iid), 7
clients, 3 seeds; test accuracy at round 5 (FedAvg under the same attacks: the earlier campaigns,
same setup):

| shares | case | FedAvg | FoolsGold | attackers' weight | honest clients left out |
|---|---|---|---|---|---|
| dirichlet | no attacker | 0.401 | 0.290 (−11.1 ± 1.0) | | 31 of 105 |
| dirichlet | 2 label flippers | 0.286 | 0.241 | 0.70, as the honest ones | 18 of 75 |
| dirichlet | omniscient ALIE, z 0.57 | 0.326 | 0.271 | 0, every round | 24 of 75 |
| dirichlet | omniscient ALIE, z 2 | 0.292 | 0.270 | 0, every round | 24 of 75 |
| dirichlet | 2 sign flippers x 10 | (collapses) | 0.175 | 0 in 18 rounds of 30 | 18 of 75 |
| iid | no attacker | 0.361 | 0.361 (0.0 ± 0.2) | | 10 of 105 |
| iid | 2 label flippers | 0.341 | 0.338 | 0.99, above the honest ones (0.70) | 14 of 75 |

- It catches what it was made for: the two omniscient attackers send the same update, and were
  left out of every round.
- It costs too much to be worth it here: on dirichlet shares, 11 points without attacker, a third
  of the honest clients' rounds left out. Their histories, summed over rounds of 3 local epochs,
  all point the way the task is learnt and look alike; the paper's clients take one SGD step per
  round. Under every attack, FoolsGold ends below FedAvg, except against sign flippers.
- Label flippers are not alike: each poisons its own data, so their histories differ as much as
  the honest clients'. FoolsGold does not see them, on either shares.
- On iid shares, it costs nothing (the honest clients left out now and then hold the same data as
  the others) and helps no more.

**Choosing**: not advised in these settings. FoolsGold answers many sybils sending the same thing;
against a few attackers with data of their own, or on heterogeneous data, `safeguard` or FLTrust
do better.

## Limits of these measurements

The campaigns compare defenses under the same conditions; they do not say how a defense behaves in
a given deployment, nor do they reproduce the papers' figures. What they leave out:

- **Few participants**: 7 clients, every one in every round, on one machine (each client is a
  process holding the model and its data, which bounds their number on one machine). Real
  federations have tens to thousands of clients, sampled each round. The robust aggregations'
  guarantees, and an attacker's estimate of the honest updates, depend on that number: the ALIE
  paper has 12 attackers among 51 workers, here 2 among 7 (5 among 20 in
  [At the paper's proportion](#at-the-papers-proportion-5-attackers-of-20)).
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
  or plants a backdoor; the client-side ALIE estimates the honest updates from 2 colluders only (5 at 20 clients).
- **Few repetitions**: 3 seeds; differences under about 1 point mean nothing, even paired (see
  [Testing them](#testing-them-the-byzantine-client)).

### Extending a campaign

Every limit above is a key of the campaign file ([campaigns.md](campaigns.md)):

| to test | change | cost |
|---|---|---|
| more participants | `clients: 20`, the attackers in `client_overrides` (e.g. 5 of them), `num_clients: 20` and `colluders: 5` for the client-side ALIE | memory and time grow with the clients; here, 7 clients took about 1 min per run, 20 clients about 1.2 GB each and 2.5 min per run of 10 rounds (`cifar10_alie_20clients.yml`): on a larger machine, or with `server_data.test.max_samples` lowered and a smaller model (`configs/mnist_cnn/`) |
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

- [Cao 2021] X. Cao, M. Fang, J. Liu, N. Z. Gong. *FLTrust: Byzantine-robust Federated Learning via
  Trust Bootstrapping*. NDSS 2021. [arXiv:2012.13995](https://arxiv.org/abs/2012.13995) — the
  `fltrust` decorator (Algorithm 2: trust score ReLU(cos), updates scaled to the server update's
  norm; root dataset of 100 examples drawn from the clients' training data, sec. VI-A).
- [Fung 2020] C. Fung, C. J. M. Yoon, I. Beschastnikh. *Mitigating Sybils in Federated Learning
  Poisoning* (v5, 2020). [arXiv:1808.04866](https://arxiv.org/abs/1808.04866) — the `foolsgold`
  decorator (Algorithm 1: history of updates, pardoning, logit of confidence κ).
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
