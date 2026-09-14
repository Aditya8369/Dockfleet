from dockfleet.core.docker_flags import build_resource_flags


def test_resource_flags_memory_only():
    config = {"resources": {"memory": "512m"}}
    flags = build_resource_flags(config)
    assert flags == ["--memory", "512m"]


def test_resource_flags_cpu_only():
    config = {"resources": {"cpu": 1.5}}
    flags = build_resource_flags(config)
    assert flags == ["--cpus", "1.5"]


def test_resource_flags_memory_and_cpu():
    config = {"resources": {"memory": "1024m", "cpu": 1.0}}
    flags = build_resource_flags(config)
    assert flags == ["--memory", "1024m", "--cpus", "1.0"]


def test_resource_flags_no_resources_key():
    config = {}
    flags = build_resource_flags(config)
    assert flags == []


def test_resource_flags_empty_resources_dict():
    config = {"resources": {}}
    flags = build_resource_flags(config)
    assert flags == []


def test_resource_flags_resources_none():
    config = {"resources": None}
    flags = build_resource_flags(config)
    assert flags == []