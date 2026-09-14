import asyncio
import logging
import subprocess

from dockfleet.core.orchestrator import get_container_name
from dockfleet.health.logs import store_log_line as store_log_line_in_db

logger = logging.getLogger(__name__)


async def stream_container_logs(service_name: str):
    """100% reliable: sync generator in async wrapper."""
    container = f"dockfleet_{service_name}"

    async def event_gen():
        max_retries = 20
        for attempt in range(max_retries):
            proc = None
            try:
                cmd = ["docker", "logs", "--tail", "5", "-f", container]
                proc = subprocess.Popen(
                    cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                    text=True, bufsize=1, universal_newlines=True
                )
                loop = asyncio.get_event_loop()
                while True:
                    line = await loop.run_in_executor(None, proc.stdout.readline)
                    if not line:
                        break
                    line = line.rstrip()
                    if line:
                        yield f"data: {line}\n\n"
                        store_log_line_in_db(service_name=service_name, message=line, source="docker-logs")

                # Check process exit code after stdout is exhausted
                try:
                    proc.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    proc.kill()
                    proc.wait()

                if proc.returncode != 0:
                    stderr_output = proc.stderr.read().strip() if proc.stderr else ""
                    if "no such container" in stderr_output.lower() or "no such image" in stderr_output.lower():
                        logger.error("Container %s does not exist: %s", container, stderr_output)
                        yield f"data: [dockfleet] Container '{container}' not found\n\n"
                        return
                    else:
                        # Other non-zero exit codes - transient, retry
                        logger.warning("Docker logs exited with code %d for %s (attempt %d/%d): %s",
                                     proc.returncode, container, attempt + 1, max_retries, stderr_output)
                else:
                    # Success (stdout exhausted normally) - exit
                    return

            except FileNotFoundError:
                logger.error("Docker binary not found. Cannot stream logs for %s", container)
                yield "data: [dockfleet] Docker is not installed or not in PATH\n\n"
                return
            except Exception as e:
                error_msg = str(e).lower()

                if "no such container" in error_msg or "no such image" in error_msg:
                    logger.error("Container %s not found: %s", container, e)
                    yield f"data: [dockfleet] Container '{container}' not found\n\n"
                    return
                elif "permission denied" in error_msg or "access is denied" in error_msg:
                    logger.error("Permission denied accessing logs for %s: %s", container, e)
                    yield f"data: [dockfleet] Permission denied accessing logs for '{container}'\n\n"
                    return
                elif "connection refused" in error_msg or "cannot connect" in error_msg:
                    logger.warning("Docker daemon unreachable for %s (attempt %d/%d): %s",
                                 container, attempt + 1, max_retries, e)
                else:
                    logger.exception("Unexpected error streaming logs for %s (attempt %d/%d)",
                               container, attempt + 1, max_retries)
                    yield f"data: [dockfleet] Error streaming logs: {e}\n\n"
                    return
            finally:
                if proc is not None:
                    try:
                        proc.terminate()
                        proc.wait(timeout=1)
                    except Exception:  # noqa: BLE001 — cleanup must not raise
                        try:
                            proc.kill()
                        except Exception:  # noqa: BLE001, S110 — best-effort kill
                            pass

            if attempt < max_retries - 1:
                await asyncio.sleep(1)

        yield "data: [dockfleet] Max retries exhausted - container may still be starting\n\n"

    async for event in event_gen():
        yield event


def stream_logs(service_name: str):
    """Sync wrapper: returns an iterator of plain log lines (no SSE formatting)."""
    container = f"dockfleet_{service_name}"
    cmd = ["docker", "logs", "--tail", "100", container]

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            logger.error("Failed to get logs for %s", container)
            return []

        for line in result.stdout.splitlines():
            line = line.rstrip()
            if line:
                yield line
    except Exception as e:
        logger.error("Failed to stream logs (sync) for %s: %s", service_name, e)
        return []


def get_logs_services(service_name: str, limit: int = 100):
    """Fetch last N logs (non-streaming)."""
    container = get_container_name(service_name)

    try:
        result = subprocess.run(
            ["docker", "logs", "--tail", str(limit), container],
            capture_output=True,
            text=True,
        )
        logs = result.stdout.strip().split("\n")
        return logs
    except Exception as e:
        return [f"Error fetching logs: {str(e)}"]


def store_log_line(service_name: str, message: str) -> None:
    """
    Backwards-compatible wrapper that stores a log line in the
    central LogEvent table via health.logs.store_log_line.
    """
    try:
        store_log_line_in_db(
            service_name=service_name,
            message=message,
            source="core.logs",
        )
    except Exception:
        logger.exception("Failed to store log line for %s", service_name)
