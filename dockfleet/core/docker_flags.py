def build_resource_flags(service_config: dict) -> list[str]:
    flags = []
    resources = service_config.get("resources") or {}
    memory = resources.get("memory")
    cpu = resources.get("cpu")
    if memory:
        flags.extend(["--memory", str(memory)])
    if cpu:
        flags.extend(["--cpus", str(cpu)])
    return flags


def build_env_flags(service_config):
    flags = []
    env = service_config.get("environment") or service_config.get("env")

    if isinstance(env, dict):
        for key, value in env.items():
            flags.extend(["-e", f"{key}={value}"])

    elif isinstance(env, list):
        for item in env:
            flags.extend(["-e", item])

    return flags


def build_port_flags(config):
    flags = []
    ports = config.get("ports") or []

    if isinstance(ports, dict):
        ports = [f"{k}:{v}" for k, v in ports.items()]

    for port in ports:
        flags.extend(["-p", port])

    return flags
