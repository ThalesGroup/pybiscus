# Logging and Tensorboard

## Tensorboard

The Pybiscus implementation of the FabricStrategy allows for a simple logging of the losses and metrics of all Clients, and the loss and the metrics of the evaluation of the Server on the (global) test dataset, if provided. The Fabric instance on the Server side has a Tensorboard logger, and everything is then simply handled.

The Tensorboard is located by default in `conf["root_dir"] + conf["logger"]["subdir"]` directory, and Fabric handles automatically the versionning of the FL session. You can then have a look at the Tensorboards by launching a tensorboard session by running, in your virtual environnment,
```bash
(.venv) tensorboard --logdir path-to-experiments --bind_all --port your-port
```

where `path-to-experiments` is `conf["root_dir"]` and `your-port` is the port of your choice for the Tensorboard server.

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

## Logging

Pybiscus uses also Rich and its nice Console to log info during the FL session, visible in the terminal. This is a nice way to check on the good processing and see if there are errors popping up.
Typer uses Rich too, especially to print nicely errors.
Flower logs some information too, dedicated in particular to the gRPC communications and the good process of the communications between Server and Clients.
