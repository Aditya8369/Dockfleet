from pathlib import Path

import pytest
import typer

from dockfleet.cli.config import load_config


def test_valid_config():
    config = load_config(Path("examples/dockfleet.yaml"))
    assert "api" in config.services
    assert config.services["api"].image == "nginx"


def test_missing_image():
    bad_yaml = """
services:
  api:
    restart: always
"""
    path = Path("tests/tmp_bad.yaml")
    path.write_text(bad_yaml)

    with pytest.raises(typer.Exit) as exc_info:
        load_config(path)
    assert exc_info.value.exit_code == 1


def test_missing_restart():
    bad_yaml = """
services:
  api:
    image: my-api:latest
"""
    path = Path("tests/tmp_bad2.yaml")
    path.write_text(bad_yaml)
    with pytest.raises(typer.Exit) as exc_info:
        load_config(path)
    assert exc_info.value.exit_code == 1
