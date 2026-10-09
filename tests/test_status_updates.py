from sqlmodel import select

from dockfleet.cli.config import DockFleetConfig, load_config
from dockfleet.health.models import ContainerStatus, Service, get_session, init_db
from dockfleet.health.services import seed_services
from dockfleet.health.status import mark_service_running, mark_service_stopped


def test_mark_service_running_and_stopped(tmp_path):
    """
    End-to-end:
    - load config
    - seed services into SQLite
    - mark one service running, then stopped
    - verify status changes in DB
    """

    # 1) Fresh DB schema
    init_db()
    with get_session() as session:
        for s in session.exec(select(Service)).all():
            session.delete(s)
        session.commit()

    # 2) Config load
    config_path = "examples/dockfleet.yaml"
    config: DockFleetConfig = load_config(config_path)

    # 3) Seed services
    with get_session() as session:
        seed_services(config, session)

    service_name = list(config.services.keys())[0]

    # 4) Status initially STOPPED
    with get_session() as session:
        svc = session.exec(select(Service).where(Service.name == service_name)).one()
        assert svc.status == ContainerStatus.STOPPED

    # 5) Mark running
    mark_service_running(service_name)

    # 6) Verify running in DB
    with get_session() as session:
        svc = session.exec(select(Service).where(Service.name == service_name)).one()
        assert svc.status == ContainerStatus.RUNNING

    # 7) Mark stopped
    mark_service_stopped(service_name)

    # 8) Verify stopped in DB
    with get_session() as session:
        svc = session.exec(select(Service).where(Service.name == service_name)).one()
        assert svc.status == ContainerStatus.STOPPED


def test_record_restart_event_persists_event(tmp_path):
    """
    Verify that record_restart_event persists the RestartEvent record for crash analytics.
    """
    from dockfleet.health.models import RestartEvent
    from dockfleet.health.status import record_restart_event

    init_db()
    with get_session() as session:
        for s in session.exec(select(Service)).all():
            session.delete(s)
        for e in session.exec(select(RestartEvent)).all():
            session.delete(e)
        session.commit()

        svc = Service(
            name="test-self-heal",
            image="nginx:alpine",
            restart_policy="always",
            status=ContainerStatus.RUNNING,
            restart_count=1,
        )
        session.add(svc)
        session.commit()
        session.refresh(svc)

    # Record first restart event
    record_restart_event(svc, "3_failed_health_checks")

    with get_session() as session:
        updated = session.exec(select(Service).where(Service.name == "test-self-heal")).one()
        assert updated.restart_count == 1
        events = session.exec(select(RestartEvent).where(RestartEvent.service_name == "test-self-heal")).all()
        assert len(events) == 1
        assert events[0].reason == "3_failed_health_checks"

    # Record second restart event
    record_restart_event(updated, "unhealthy_restart")

    with get_session() as session:
        updated2 = session.exec(select(Service).where(Service.name == "test-self-heal")).one()
        assert updated2.restart_count == 1
        events = session.exec(select(RestartEvent).where(RestartEvent.service_name == "test-self-heal")).all()
        assert len(events) == 2


