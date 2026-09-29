
# Session using the manager

## Install Pybiscus
After cloning the repo and installing (via uv) all dependencies, you have to extend your PATH with the command:
```bash
source ./extend_path.sh
```

The session manager ensures consistency across federation participants, handles registration, synchronization, and shared settings.

### Init of the session

launch the session manager :

```bash
./launch/session/run_manager.sh
```

connect to http://localhost:5555/pybiscus-session/manage

The session configuration (server agent) has an optional `data_partition` block: when set, the
manager shares the training data between the clients registered when the session is launched, each
client getting its `partition_id` (its rank) and the number of partitions, locked in its form, along
with a stable `cid` equal to that rank.

Its `share_cpu_threads` setting (on by default) shares the CPU of each machine between the clients
running on it: each agent tells the manager its machine and number of physical cores when it
registers, and each client gets `client_compute_context.num_threads` = cores / clients on its
machine (still editable in its form). Without it, every PyTorch client takes all the cores: three
cifar10 clients on a 14-core machine took 233 s per round instead of 20 s.

The manager listens on 127.0.0.1 by default. When agents run on other hosts (they send it their
registration and logs), start it with `--host 0.0.0.0` (or a given address), e.g.
`launch/session/run_manager.sh --host 0.0.0.0`.

![Session Manager init](images/session_manager_init.png "Session Manager init")

### Init of the agents

launch the server agent :

```bash
 ./launch/agent/cli/5000.sh
```

launch the client1 agent :

```bash
 ./launch/agent/cli/5001.sh
```

launch the client2 agent :

```bash
 ./launch/agent/cli/5002.sh
```

![Session Manager agents started](images/session_manager_agents_started.png "Session Manager agents started")

### Init of the session : server side

connect to http://localhost:5000/session/agent/registration

![Server registration](images/session_server_registration.png "Server registration")

sets the parameters and register agent, it now waits for the session start

![Server waiting](images/session_server_waiting.png "Server waiting")

![Session configuration](images/session_manager_config.png "Session configuration")

### Init of the session : client 1 side


connect to http://localhost:5001/session/client/registration

![Client1 registration](images/session_client1_registration.png "Client1 registration")

and the client 1 registers to the session

### Init of the session : client 2 side


connect to http://localhost:5002/session/client/registration

![Client2 registration](images/session_client2_registration.png "Client2 registration")

and the client 2 registers to the session

### Session shared parameters setting
 
As soon as the server is registered,
the manager connect to it in order to set the session common parameters
(flower server access, used data and model)

![Session configuration 2](images/session_manager_config2.png "Session configuration 2")

Proceed to the session common parameters definition, 
the server and clients will pass to the configuration phasis with the session common parameters set and locked (lock image in the field name)

For instance, configurate its metrics logging feature and logging feature to use a webhook :

![Server webhook 1](images/session_server_webhook1.png "Server webhook 1")

![Server webhook 2](images/session_server_webhook2.png "Server webhook 2")

Check and Execute the server configuration.

### Session run : client 1 side

Check and Execute the client1 configuration.

![Session Run Client1](images/session_client1.png "Session Run Client1")

### Session run : client 2 side

Check and Execute the client2 configuration.

![Session Run Client2](images/session_client2.png "Session Run Client2")

You can see directly the logs and metrics in the session manager, instead of having to look in each agent terminal (as we configurate them to the web-hook option).

### Session monitoring 

running session

![Session Run Information 1](images/session_manager_runinfo1.png "Session Run Information 1")

finished session

![Session Run Information 2](images/session_manager_runinfo2.png "Session Run Information 2")
