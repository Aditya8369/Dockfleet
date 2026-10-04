import asyncio
from datetime import datetime, timedelta, timezone

import httpx
from httpx import ASGITransport
from sqlmodel import select

from dockfleet.dashboard.api import app
from dockfleet.health.models import LogEvent, Service, get_session, init_db


def setup_function(_func):
    init_db()
    with get_session() as session:
        session.exec(select(LogEvent)).all()
        session.exec(select(Service)).all()
        for row in session.exec(select(LogEvent)).all():
            session.delete(row)
        for row in session.exec(select(Service)).all():
            session.delete(row)
        session.commit()


def test_explore_logs_returns_both_aware_and_naive_utc_records():
    """Verify explore_logs returns records created in the last 24h regardless of tz-aware/naive UTC."""
    now_utc = datetime.now(timezone.utc)
    now_naive = now_utc.replace(tzinfo=None)

    with get_session() as session:
        svc = Service(
            name="api",
            image="api:latest",
            restart_policy="always",
        )
        session.add(svc)
        session.commit()
        session.refresh(svc)

        # 1. Log created 2 hours ago (timezone-aware UTC) - within 24h
        session.add(
            LogEvent(
                service_id=svc.id,
                service_name="api",
                created_at=now_utc - timedelta(hours=2),
                message="aware log within 24h",
            )
        )
        # 2. Log created 5 hours ago (naive UTC) - within 24h
        session.add(
            LogEvent(
                service_id=svc.id,
                service_name="api",
                created_at=now_naive - timedelta(hours=5),
                message="naive log within 24h",
            )
        )
        # 3. Log created 30 hours ago (timezone-aware UTC) - outside 24h
        session.add(
            LogEvent(
                service_id=svc.id,
                service_name="api",
                created_at=now_utc - timedelta(hours=30),
                message="aware log older than 24h",
            )
        )
        # 4. Log created 35 hours ago (naive UTC) - outside 24h
        session.add(
            LogEvent(
                service_id=svc.id,
                service_name="api",
                created_at=now_naive - timedelta(hours=35),
                message="naive log older than 24h",
            )
        )
        session.commit()

    async def _run():
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            return await client.get("/logs/explore/api")

    response = asyncio.run(_run())
    assert response.status_code == 200
    data = response.json()

    assert len(data) == 2
    messages = [item["message"] for item in data]
    assert "aware log within 24h" in messages
    assert "naive log within 24h" in messages
    assert "aware log older than 24h" not in messages
    assert "naive log older than 24h" not in messages


def test_explore_logs_custom_days_parameter():
    """Verify explore_logs respects the custom `days` parameter."""
    now_utc = datetime.now(timezone.utc)
    now_naive = now_utc.replace(tzinfo=None)

    with get_session() as session:
        svc = Service(
            name="worker",
            image="worker:latest",
            restart_policy="always",
        )
        session.add(svc)
        session.commit()
        session.refresh(svc)

        # Log created 2 days ago
        session.add(
            LogEvent(
                service_id=svc.id,
                service_name="worker",
                created_at=now_utc - timedelta(days=2),
                message="worker log 2 days ago",
            )
        )
        # Log created 5 days ago
        session.add(
            LogEvent(
                service_id=svc.id,
                service_name="worker",
                created_at=now_naive - timedelta(days=5),
                message="worker log 5 days ago",
            )
        )
        # Log created 10 days ago
        session.add(
            LogEvent(
                service_id=svc.id,
                service_name="worker",
                created_at=now_utc - timedelta(days=10),
                message="worker log 10 days ago",
            )
        )
        session.commit()

    async def _run(days: int):
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            return await client.get(f"/logs/explore/worker?days={days}")

    # Query with days=3 (should include 2 days ago, exclude 5 and 10 days ago)
    response_3d = asyncio.run(_run(3))
    assert response_3d.status_code == 200
    data_3d = response_3d.json()
    assert len(data_3d) == 1
    assert data_3d[0]["message"] == "worker log 2 days ago"

    # Query with days=7 (should include 2 and 5 days ago, exclude 10 days ago)
    response_7d = asyncio.run(_run(7))
    assert response_7d.status_code == 200
    data_7d = response_7d.json()
    assert len(data_7d) == 2
    messages_7d = [item["message"] for item in data_7d]
    assert "worker log 2 days ago" in messages_7d
    assert "worker log 5 days ago" in messages_7d
    assert "worker log 10 days ago" not in messages_7d


def test_explore_logs_filters_by_service():
    """Verify explore_logs only returns logs for the requested service."""
    now_utc = datetime.now(timezone.utc)

    with get_session() as session:
        svc_a = Service(name="svc-a", image="img:latest", restart_policy="always")
        svc_b = Service(name="svc-b", image="img:latest", restart_policy="always")
        session.add_all([svc_a, svc_b])
        session.commit()
        session.refresh(svc_a)
        session.refresh(svc_b)

        session.add(
            LogEvent(
                service_id=svc_a.id,
                service_name="svc-a",
                created_at=now_utc - timedelta(minutes=10),
                message="message for svc-a",
            )
        )
        session.add(
            LogEvent(
                service_id=svc_b.id,
                service_name="svc-b",
                created_at=now_utc - timedelta(minutes=10),
                message="message for svc-b",
            )
        )
        session.commit()

    async def _run():
        async with httpx.AsyncClient(
            transport=ASGITransport(app=app), base_url="http://testserver"
        ) as client:
            return await client.get("/logs/explore/svc-a")

    response = asyncio.run(_run())
    assert response.status_code == 200
    data = response.json()
    assert len(data) == 1
    assert data[0]["message"] == "message for svc-a"
