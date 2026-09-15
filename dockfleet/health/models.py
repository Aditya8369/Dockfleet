import logging
from datetime import datetime
from enum import Enum
from pathlib import Path

import sqlalchemy
from sqlmodel import Field, SQLModel, create_engine

logger = logging.getLogger(__name__)


class ContainerStatus(str, Enum):
    """
    Container lifecycle state enumeration.

    - RUNNING: Container is active and executing.
    - STOPPED: Container has exited cleanly or was stopped manually.
    - UNKNOWN: Container state cannot be determined or is missing from Docker daemon.
    """

    RUNNING = "running"
    STOPPED = "stopped"
    UNKNOWN = "unknown"


class HealthStatus(str, Enum):
    """
    Health check status enumeration.

    - HEALTHY: Service passes health checks or is in a normal clean state.
    - UNHEALTHY: Service is failing health checks (external/API dimension).
    - CRASHED: Service failed consecutive health checks or exited unexpectedly.
    - RESTARTING: Service container restart is actively in progress.
    """

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    CRASHED = "crashed"
    RESTARTING = "restarting"


class SafeContainerStatusType(sqlalchemy.types.TypeDecorator):
    """Resilient Enum storage for ContainerStatus with safe fallback for corrupted legacy data."""

    impl = sqlalchemy.types.String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Serialize ContainerStatus enum member or string to plain string for SQL storage."""
        if value is None:
            return ContainerStatus.UNKNOWN.value
        if isinstance(value, ContainerStatus):
            return value.value
        return str(value)

    def process_result_value(self, value, dialect):
        """Deserialize database string into ContainerStatus with warning logging on fallback."""
        if not value:
            # Empty or missing container status indicates undetermined state.
            logger.warning(
                "Empty or null ContainerStatus value %r in database, coercing to UNKNOWN",
                value,
            )
            return ContainerStatus.UNKNOWN
        try:
            return ContainerStatus(value)
        except (ValueError, KeyError):
            # Garbage or invalid container status string cannot be resolved to running/stopped.
            logger.warning(
                "Unrecognized ContainerStatus value %r in database, coercing to UNKNOWN",
                value,
            )
            return ContainerStatus.UNKNOWN


class SafeHealthStatusType(sqlalchemy.types.TypeDecorator):
    """Resilient Enum storage for HealthStatus with safe fallback for corrupted legacy data."""

    impl = sqlalchemy.types.String
    cache_ok = True

    def process_bind_param(self, value, dialect):
        """Serialize HealthStatus enum member or string to plain string for SQL storage."""
        if value is None:
            return HealthStatus.HEALTHY.value
        if isinstance(value, HealthStatus):
            return value.value
        return str(value)

    def process_result_value(self, value, dialect):
        """Deserialize database string into HealthStatus with warning logging on fallback."""
        if not value:
            # Uninitialized / legacy records created before health tracking default to HEALTHY.
            logger.warning(
                "Empty or null HealthStatus value %r in database, coercing to HEALTHY",
                value,
            )
            return HealthStatus.HEALTHY
        try:
            return HealthStatus(value)
        except (ValueError, KeyError):
            # Garbage / corrupted health string triggers defensive degradation to UNHEALTHY.
            logger.warning(
                "Unrecognized HealthStatus value %r in database, coercing to UNHEALTHY",
                value,
            )
            return HealthStatus.UNHEALTHY


class Service(SQLModel, table=True):
    """
    Service database table model representing a managed service and its runtime state.
    """

    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(nullable=False, unique=True)
    image: str = Field(nullable=False)
    restart_policy: str = Field(nullable=False)
    # Serialized config fields
    ports_raw: str | None = Field(default=None)
    healthcheck_raw: str | None = Field(default=None)
    # Runtime state fields
    # status: container lifecycle (running / stopped / unknown)
    status: ContainerStatus = Field(
        default=ContainerStatus.UNKNOWN,
        sa_type=SafeContainerStatusType,
        nullable=False,
    )
    # health_status: health dimension (healthy / crashed / restarting / unhealthy)
    health_status: HealthStatus = Field(
        default=HealthStatus.HEALTHY,
        sa_type=SafeHealthStatusType,
        nullable=False,
    )
    restart_count: int = Field(default=0, nullable=False)
    last_health_check: datetime | None = Field(default=None)
    last_failure_reason: str | None = Field(default=None)
    consecutive_failures: int = Field(default=0, nullable=False)
    # Extra config for future dashboard / analytics
    # Example: resources.memory: "512m", resources.cpu: 0.5
    resources_memory: str | None = Field(default=None)
    resources_cpu: float | None = Field(default=None)
    # environment and depends_on stored in serialized form
    # env_raw: JSON string (e.g. '["DB_URL=postgres://...", "REDIS_URL=..."]')
    # depends_on_raw: comma-separated service names (e.g. "redis,db")
    env_raw: str | None = Field(default=None)
    depends_on_raw: str | None = Field(default=None)


class RestartEvent(SQLModel, table=True):
    """
    Historical restart event record for analytics and crash diagnostics.
    """

    id: int | None = Field(default=None, primary_key=True)
    service_id: int = Field(nullable=False, foreign_key="service.id")
    # Denormalized service name for easier analytics queries
    service_name: str = Field(nullable=False, index=True)
    restarted_at: datetime = Field(nullable=False, index=True)
    reason: str = Field(nullable=False)
    previous_status: str | None = Field(default=None)
    new_status: str | None = Field(default=None)


# LogEvent table model (log metadata skeleton)
# fields: id, service_id, service_name, created_at, level, message, source
class LogEvent(SQLModel, table=True):
    """
    Lightweight log metadata row for future log aggregation / crash analytics.
    Raw Docker logs will still be streamed separately; this table stores
    small, query-friendly summaries (who, when, what, where-from).
    """

    id: int | None = Field(default=None, primary_key=True)
    service_id: int = Field(nullable=False, foreign_key="service.id")
    # Index on service_name for fast per-service queries
    service_name: str = Field(nullable=False, index=True)
    # Index on created_at for time-ordered scans
    created_at: datetime = Field(nullable=False, index=True)
    # Optional metadata fields
    level: str | None = Field(default=None)  # e.g. "INFO", "WARN", "ERROR"
    message: str | None = Field(default=None)  # short summary / first line
    source: str | None = Field(
        default=None
    )  # e.g. "docker-logs", "scheduler", "orchestrator"


# init_db() function
# work: engine + tables create
PROJECT_ROOT = Path(__file__).resolve().parents[2]
DB_PATH = PROJECT_ROOT / "dockfleet.db"
sqlite_file_name = str(DB_PATH)
sqlite_url = f"sqlite:///{sqlite_file_name}"
engine = create_engine(sqlite_url, connect_args={"timeout": 30})


def init_db() -> None:
    """Initialize the SQLite database and create all missing tables."""
    SQLModel.metadata.create_all(engine)
