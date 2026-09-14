# tests/test_services_from_config.py
from dockfleet.cli.config import DockFleetConfig, load_config
from dockfleet.health.services import services_from_config


def main() -> None:
    config_path = "examples/dockfleet.yaml"
    config: DockFleetConfig = load_config(config_path)

    print("Loaded services from config.yml:")
    print(list(config.services.keys()))
    print("-" * 60)

    services = services_from_config(config)

    print(f"services_from_config produced {len(services)} Service objects\n")

    for svc in services:
        print(
            f"name={svc.name!r}, "
            f"image={svc.image!r}, "
            f"restart_policy={svc.restart_policy!r}, "
            f"ports_raw={svc.ports_raw!r}, "
            f"healthcheck_raw={svc.healthcheck_raw!r}, "
            f"status={svc.status!r}, "
            f"restart_count={svc.restart_count}"
        )

    print("-" * 60)


if __name__ == "__main__":
    main()
