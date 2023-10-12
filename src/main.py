import typer

import src.flower.client_fabric as client
import src.flower.local_train as local_train
import src.flower.server_fabric as server

app = typer.Typer(pretty_exceptions_show_locals=False, rich_markup_mode="markdown")
app.add_typer(server.app, name="server")
app.add_typer(client.app, name="client")
app.add_typer(local_train.app, name="local")


@app.callback()
def explain():
    """

    **The Pybiscus app is made of three commands:**

    * server

    * client

    * local: to train locally a model.

    ---

    Build on top of Flower using Typer for the CLI and script parts,
    Lightning and Fabric for the ML parts.
    """


if __name__ == "__main__":
    app()
