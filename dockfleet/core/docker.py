import subprocess


class DockerManager:
    def create_network(self, name: str):
        try:
            subprocess.run(
                ["docker", "network", "create", name],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
        except subprocess.CalledProcessError:
            # network probably already exists
            pass

    def run_container(self, image, name, flags=None, network=None):

        cmd = ["docker", "run", "-d", "--name", name]

        if network:
            cmd += ["--network", network]

        if flags:
            cmd += flags

        cmd.append(image)

        subprocess.run(cmd, check=True)

    def remove_container(self, name):

        result = subprocess.run(
            ["docker", "rm", "-f", name], capture_output=True, text=True
        )

        if result.returncode != 0:
            if "No such container" in result.stderr:
                return
            else:
                raise RuntimeError(result.stderr)

    def stop_container(self, name):
        subprocess.run(["docker", "stop", name], check=True)

    def list_containers(self):
        subprocess.run(["docker", "ps"], check=True)
