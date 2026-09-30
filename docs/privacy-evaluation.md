# Privacy evaluation: FedMIA

The `fedmiaprivacyevaluation` strategy decorator (plugin
`pybiscus-plugins/strategydecorator/clientprivacyevaluation`, contributed in PR #44) runs a
membership inference attack from the server: every round, for each example of a *privacy set* and
each client, it scores how much the client's update looks like it was trained on that example
(cosine between the example's gradient and the client's update, and the example's loss before and
after the client's training). An analyser then compares these scores to which client really trained
on which example, and plots ROC curves.

It measures what an honest-but-curious **server** can infer from each client's own update.
Server-side differential privacy (`serverdpfixed`, `serverdpadaptive`) noises only the aggregated
model, not these updates: it is not expected to lower this attack's success.

## Configuration

The server's data section gives the attacked examples (`privacy`, see
[configuration.md](configuration.md#data)): the official train split in its order, so that example
*i* of the privacy set is example *i* of the clients' partitions.

```yaml
server_strategy:
  pipeline:
  - name: fedmiaprivacyevaluation
    config:
      reporting_sub_dir: rounds
      criterion: CrossEntropyLoss   # model_val: the model returns its loss from (x, target), as FasterRCNN
  ...
data:
  name: cifar
  config:
    test:
      dir: ${root_dir}/datasets/test/
    privacy:
      dir: ${root_dir}/datasets/train/
      max_samples: 2000            # the attack computes one gradient per example, per round
```

Without a privacy set, the server refuses to start. Every round writes, under
`<experiment>/rounds/round_<n>/`, the parameters each client received and returned (`.npz`, one
model per client and round: mind the disk space), `cosine_matrix.csv` and `loss_per_instances.csv`
(one row per attacked example, `Image_idx` = its index in the train split, one column per client
`cid`).

The clients must train on their whole share: with `train.max_samples`, a client trains on part of
it while the exported indices list all of it, counting untrained examples as members.

## Running it

A demo lives in `configs/cifar10_cnn/distributed/without_ssl/with_privacy_eval_cpu/` (one server,
two clients, each on half of the train split). The campaign tool runs it with three clients:

```bash
uv run python launch/campaign/strategy_campaign.py launch/campaign/cifar10_fedmia.yml
```

Then, the clients' memberships and the analysis:

```bash
uv run python pybiscus/main.py data partition <a client config> --export experiments/partition
uv run python pybiscus-plugins/strategydecorator/clientprivacyevaluation/fedmiaprivacy_analyser.py \
    --round-path <experiment>/rounds --ground-truth-folder experiments/partition \
    --save-folder plots --plot_per_label false
```

The analyser prints each client's AUC (all rounds, then per round) and saves the ROC curves.
`--plot_per_label true` adds one curve per class when the indices folder holds an
`index_to_label.csv`.

A sanity check: export the partitions again with another `train.partition.seed`; the AUC against
those (random) memberships must fall to about 0.5. On cifar10 (3 clients, iid, 3 rounds, 2000
attacked examples), the loss attack reached 0.55 to 0.58 with 5 local epochs (0.51 to 0.54 with one)
against 0.50 to 0.52 for the random memberships: the more the clients fit their data, the more the
attack succeeds.
