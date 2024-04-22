from typer.testing import CliRunner

from pybiscus.main import app

runner = CliRunner()


def test_app_client():
    result = runner.invoke(app, ["client", "check", "configs/client_1.yml"])
    assert result.exit_code == 0


def test_app_client_on_server():
    result = runner.invoke(app, ["client", "check", "configs/server.yml"])
    assert result.exit_code == 1
