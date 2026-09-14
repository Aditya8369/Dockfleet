def build_resource_flags(service_config: dict) -> list[str]:

    flags = []

    memory = service_config.get("memory")
    cpus = service_config.get("cpus")

    if memory:
        flags.extend(["--memory", str(memory)])

    if cpus:
        flags.extend(["--cpus", str(cpus)])

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
