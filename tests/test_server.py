from typer.testing import CliRunner

from src.main import app

runner = CliRunner()


def test_app_server():
    result = runner.invoke(app, ["server", "check", "configs/server.yml"])
    assert result.exit_code == 0


def test_app_server_on_client():
    result = runner.invoke(app, ["server", "check", "configs/client_1.yml"])
    assert result.exit_code == 1
