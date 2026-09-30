# Robust aggregation against malicious clients

The strategies of the `flowergeneric` plugin include aggregations meant to resist malicious
(byzantine) clients: `fedmedian`, `fedtrimmedavg` (`beta`: fraction trimmed on each side), `krum`
(`num_malicious_clients` f, `num_clients_to_keep` > 0 for Multi-Krum) and `bulyan`
(`num_malicious_clients` f; needs at least 4f + 3 clients, which `server check` enforces on
`min_fit_clients`: below, Flower fails in the middle of the aggregation).

## Testing them: the `byzantine` client

`pybiscus-plugins/client/byzantine` is a client that trains honestly, then alters its update
delta = w_trained − w_global before sending it:

| `attack` | sent | |
|---|---|---|
| `sign_flip` (`scale`) | w_global − scale · delta | pulls the model the wrong way |
| `scale` (`scale`) | w_global + scale · delta | dominates the aggregate |
| `gaussian` (`stddev`) | w_global + noise | a faulty client |
| `none` | the honest update | with `num_examples_factor`, lies about its size only |

`from_round` delays the attack, `seed` fixes the noise; the client reports a `byzantine` metric.
It is a test tool: it is declared in `launch/campaign/test-plugins-conf.yml` only, never in the
default manifest, so that it does not appear in a real session's forms. A client uses it through
`flower_client.alternate_client_class: {name: byzantine, config: {...}}`, with the test manifest
added: `PYBISCUS_PLUGIN_CONF_PATH=pybiscus-plugins-conf.yml:launch/campaign/test-plugins-conf.yml`.

The campaign tool takes the extra manifests (`plugin_manifests`) and per-client settings for a
variant (`client_overrides`, by client number):

```bash
uv run python launch/campaign/strategy_campaign.py launch/campaign/cifar10_robust.yml
```

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

Bounding the norm of each client's update before the mean keeps FedAvg's accuracy while limiting
what one client can do. `serverdpfixed` with `noise_multiplier: 0` does exactly that (clipping of
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
  target))`), and C decreased every round while 86 % of the updates were clipped. It also noised
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
```

- `median` sets C by itself every round, without lag, and a minority of clients cannot move the
  median.
- The update is measured against what each client was sent: listed after
  `personalizeclientsfitin` (enforced at check), it follows the personalized models. It cannot be
  combined with the server-side DP decorators, which clip already.
- Every round logs `clip_norm`, `clip_fraction`, the median and maximum update norms, the clipped
  clients, and for each client `clip_ratio_<cid>` = its update norm / the median: a client clipped
  round after round far above the median is a suspect.

Dirichlet shares, same attackers:

| variant | no attacker | 1 attacker | 2 attackers |
|---|---|---|---|
| FedAvg | 0.398 | 0.102 | — |
| clipping, median x 1.5 | 0.396 | 0.298 | 0.210 |
| clipping, median x 2 | 0.389 | 0.266 | 0.091 |
| Bulyan, f 1 | 0.333 | 0.348 | — |

- Without attacker, median x 1.5 costs nothing (one honest client clipped once in 5 rounds).
- The attackers were exactly the clipped clients every round (`clip_ratio` about 9.2 against 1.0).
- Clipping limits an attacker without removing it: its update, brought down to 1.5 times the
  median, still pulls the wrong way. Under attack, Bulyan does better; with several attackers,
  clipping alone does not hold.

**Choosing**: no attack expected, heterogeneous data → FedAvg (+ `clipping`, median x 1.5, as a
free safeguard and a detector); attacks expected → Bulyan (on iid-like data, Multi-Krum too).
