import typer
from trogon import Trogon
from typer.main import get_group

import src.commands.app_client as client
import src.commands.app_local as local_train
import src.commands.app_server as server

app = typer.Typer(pretty_exceptions_show_locals=False, rich_markup_mode="rich")
app.add_typer(server.app, name="server")
app.add_typer(client.app, name="client")
app.add_typer(local_train.app, name="local")


@app.command()
def tui(ctx: typer.Context):
    Trogon(get_group(app), click_context=ctx).run()


@app.callback()
def explain():
    """

    **The Pybiscus app is made of three commands:**

    * server: to launch a server for a Federated Learning session.

    * client: to launch a client for a Federated Learning session.

    * local: to train locally a model.

    ---

    Build on top of Flower using Typer for the CLI and script parts,
    Lightning and Fabric for the ML parts.
    """

