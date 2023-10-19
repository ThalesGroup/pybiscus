# How to use config files

Here are a few hints about how to use and customize the config files (server, client).

## Fabric

The keyword `fabric` holds a dictionnary of keywords to use by the Fabric instance. It is used by both Server and Clients. The keywords and their types are simply the one provided by the Fabric API.

Here is an example from the file `configs/server.yml`:

```yaml
...
fabric:
  accelerator: gpu
  devices:
    - 0
...
```

The keyword `devices` is waiting for either a list of integers (the id of the devices themselves) or an integer (for the number of devices wanted). To use CPU for instance, you can simply write
```yaml
...
fabric:
  accelerator: cpu
  # devices: 
...
```

The keyword `devices` is left intentionnaly commented, as Fabric will automatically find a suitable device corresponding to the choice cpu.

## Models

## Data

## Others