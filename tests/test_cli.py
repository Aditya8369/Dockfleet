from typer.testing import CliRunner
from unittest.mock import patch

from dockfleet.cli.main import app

runner = CliRunner()


def test_cli_validate_success():
    result = runner.invoke(app, ["validate", "examples/dockfleet.yaml"])
    assert result.exit_code == 0
    assert "Config valid" in result.stdout


def test_cli_validate_invalid_schema(tmp_path):
    bad_config = tmp_path / "bad.yaml"
    bad_config.write_text("""
services:
  web:
    image: nginx
    resources:
      cpu: -1.0
""")
    result = runner.invoke(app, ["validate", str(bad_config)])
    assert result.exit_code == 1
    assert "Unexpected error:" not in result.stdout
    assert "Configuration Validation Error" in result.output


@patch("dockfleet.cli.main.Orchestrator.restart")
def test_cli_restart(mock_restart):
    """Test that the restart command executes successfully without crashing."""
    result = runner.invoke(app, ["restart", "examples/dockfleet.yaml"])
    assert result.exit_code == 0
    assert "Restarting services from" in result.stdout
    mock_restart.assert_called_once()


@patch("dockfleet.cli.main.Orchestrator.restart")
def test_cli_restart_failure(mock_restart):
    """Test that the restart command handles and exits with code 1."""
    mock_restart.side_effect = RuntimeError("Failed to stop services")
    result = runner.invoke(app, ["restart", "examples/dockfleet.yaml"])
    assert result.exit_code == 1
    assert "Error restarting services" in result.stdout


@patch("dockfleet.core.orchestrator.mark_service_stopped")
@patch("dockfleet.core.docker.DockerManager.remove_container")
@patch("dockfleet.core.docker.DockerManager.stop_container")
@patch("dockfleet.core.orchestrator.Orchestrator.up")
def test_cli_restart_absent_container(mock_up, mock_stop, mock_remove, mock_mark):
    """Regression test: restart proceeds when the configured container does not exist."""
    # Simulate Docker throwing a "No such container" error during down()
    mock_stop.side_effect = Exception("Error: No such container: dockfleet_api")

    # Run the restart command
    result = runner.invoke(app, ["restart", "examples/dockfleet.yaml"])

    # Ensure it didn't crash and successfully reached up()
    assert result.exit_code == 0
    mock_up.assert_called_once()
