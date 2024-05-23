from jsonargparse import ActionConfigFile, ArgumentParser
from rich.traceback import install

from pybiscus.console import console
from pybiscus.flower.server_fabric import Server

install()


def server_cli():
    parser = ArgumentParser(description="This is it!", parser_mode="omegaconf")
    # parser.add_argument("--config_server", type=ConfigServer)
    parser.add_class_arguments(Server, "server.init")
    parser.add_method_arguments(Server, "launch", "server.launch")

    parser.add_argument("--config", action=ActionConfigFile)

    cfg = parser.parse_args()
    console.log(cfg.as_dict())
    cfg = parser.instantiate_classes(cfg)
    console.log(cfg)
    server = cfg.server.init
    console.log(server)
    server.launch(**cfg.server.launch.as_dict())


if __name__ == "__main__":
    server_cli()
