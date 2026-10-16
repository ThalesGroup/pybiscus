import signal

# SIGINT/SIGTERM/SIGQUIT are taken by Flower's immediate shutdown; Windows has no SIGUSR1.
# Apart from the server, in a module of its own: the agent, which sends it, does not import flwr
STOP_SIGNAL = getattr(signal, "SIGUSR1", None)
