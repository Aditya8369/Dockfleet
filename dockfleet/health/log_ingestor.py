from __future__ import annotations

import subprocess
import tempfile
from datetime import datetime, timedelta, timezone

from sqlmodel import select

from .models import LogCursor, LogEvent, Service, get_session


def _parse_docker_timestamp(ts_str: str) -> datetime | None:
    """Parse RFC3339 / ISO 8601 Docker log timestamp into UTC datetime."""
    try:
        dt = datetime.fromisoformat(ts_str)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError):
        pass
    try:
        if ts_str.endswith("Z"):
            dt = datetime.fromisoformat(ts_str[:-1] + "+00:00")
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
    except Exception:
        pass
    return None


def ingest_docker_logs_once(tail: int = 200) -> None:
    """
    Pull last `tail` docker logs for every known Service and store them
    into LogEvent for /logs/db and /logs/download.
    """
    with get_session() as session:
        services = session.exec(select(Service)).all()

        for svc in services:
            name = svc.name
            svc_id = svc.id
            container = f"dockfleet_{name}"

            # Fetch docker source timestamp cursor
            cursor_row = session.exec(
                select(LogCursor).where(LogCursor.service_id == svc_id)
            ).one_or_none()
            cursor_ts_str = cursor_row.last_timestamp if cursor_row else None

            cmd = ["docker", "logs", "--timestamps"]
            if cursor_ts_str is not None:
                cmd.extend(["--since", cursor_ts_str])
            else:
                cmd.extend(["--tail", str(tail)])
            cmd.append(container)

            try:
                process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.PIPE,
                    stderr=subprocess.DEVNULL,
                    text=True,
                )
            except (subprocess.SubprocessError, OSError) as e:
                print(f"Error streaming docker logs for {name}: {e}")
                continue

            with tempfile.TemporaryFile(mode="w+t") as spool:
                # Stage to disk (tempfile) to avoid memory blowup while we wait for success
                for line in process.stdout:
                    line = line.rstrip()
                    if line:
                        spool.write(line + "\n")
                
                process.stdout.close()
                if process.wait() != 0:
                    session.rollback()
                    continue

                spool.seek(0)
                batch_count = 0
                last_source_ts = None
                
                for line in spool:
                    line = line.rstrip()
                    if not line:
                        continue
                        
                    message = line
                    log_created_at = None
                    if " " in line:
                        ts_str, msg = line.split(" ", 1)
                        if ts_str.startswith("20") and ts_str.endswith("Z"):
                            last_source_ts = ts_str
                            message = msg
                            log_created_at = _parse_docker_timestamp(ts_str)
                    
                    if log_created_at is None:
                        log_created_at = datetime.now(timezone.utc)

                    event = LogEvent(
                        service_id=svc_id,
                        service_name=name,
                        created_at=log_created_at,
                        level=None,
                        message=message,
                        source="docker-logs-ingestor",
                    )
                    session.add(event)
                    
                    batch_count += 1
                    if batch_count >= 1000:
                        if last_source_ts:
                            if not cursor_row:
                                cursor_row = LogCursor(service_id=svc_id, last_timestamp=last_source_ts)
                                session.add(cursor_row)
                            else:
                                cursor_row.last_timestamp = last_source_ts
                        session.commit()
                        batch_count = 0

                if batch_count > 0:
                    if last_source_ts:
                        if not cursor_row:
                            cursor_row = LogCursor(service_id=svc_id, last_timestamp=last_source_ts)
                            session.add(cursor_row)
                        else:
                            cursor_row.last_timestamp = last_source_ts
                    session.commit()
