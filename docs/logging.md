# Logging and Tensorboard

## What a session leaves

Each server run reports into `server_run.reporting.basedir` (`${root_dir}/experiments` by
default), in a sub-directory named after its start time (`add_timestamp_in_path`); `current`
links to the last one:

- `server_logs.txt`: the server's log lines;
- `metrics.txt`: every metric the server logged, round by round (the clients' fit and evaluation
  metrics, `fit_<metric>_<cid>`, `val_<metric>_<cid>`, and its own evaluation, `val_<metric>_glob`);
- the configuration it ran with (`server_config_filename`), the final weights
  (`save_on_train_end`), the ONNX export, and what the decorators save (`rounds/`).

These two files are always written. The server's `server_run.loggers` (where its log lines go)
and `server_compute_context.metrics_loggers` (where its metrics go) add other destinations.

## Tensorboard

The `tensorboard` metrics logger writes the same metrics for TensorBoard, under
`<reporting directory>/<subdir>/lightning_logs/` (`subdir: tensorboard` by default):

```yaml
server_compute_context:
  metrics_loggers:
  - name: tensorboard
    config:
      subdir: tensorboard
```

```bash
uv run tensorboard --logdir experiments/current/tensorboard/lightning_logs --bind_all --port 6006
```

(`bin/show_tensorboard_server.sh` does the same from inside a reporting directory.)

## Webhooks: the session manager

The `webhook` logger (`server_run.loggers`) and the `webhook` metrics logger
(`server_compute_context.metrics_loggers`) post the log lines and the metrics to the session
manager, which shows them live (`/webhook/logs`, `/webhook/metrics`). The agents' server form has
both by default.

## Weights & Biases

The `wandb` metrics logger sends the server's metrics (global evaluation and every client's
metrics, per round) to a Weights & Biases run, with the whole server configuration as the run's
config:

```yaml
server_compute_context:
  metrics_loggers:
  - name: tensorboard
    config:
      subdir: tensorboard
  - name: wandb
    config:
      project: pybiscus          # entity, name, group: optional; tags: a list
      mode: online               # online | offline | disabled
      api_key_env_var: WANDB_API_KEY
```

- `online` needs an API key: in the environment variable named by `api_key_env_var` (read only
  when present, for this run only), or from a `wandb login` done on the server's machine. The key
  itself is never put in the configuration: it is saved with the experiment and shown in the
  agent's forms. Without a key, the server stops with a message saying so.
- `offline` needs no account nor network: the run is kept in `<experiment>/wandb/offline-run-…`,
  and `wandb sync <that directory>` sends it later, from a machine that has access.
- The run's files always go to the experiment directory, not to a `./wandb` of the current one.

## Console

The `rich` logger prints the log lines in the terminal with Rich's console; Typer uses Rich too, to
print errors. Flower logs its own lines, about the gRPC communications between the server and the
clients.
