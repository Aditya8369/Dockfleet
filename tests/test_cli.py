from typer.testing import CliRunner

from dockfleet.cli.main import app

runner = CliRunner()


def test_cli_validate_success():
    result = runner.invoke(app, ["validate", "examples/dockfleet.yaml"])
    assert result.exit_code == 0
    assert "Config valid" in result.stdout
