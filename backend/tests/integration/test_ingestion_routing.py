from pathlib import Path

from codefixer.application.ports.tickets import TicketBatch
from codefixer.application.services.ingestion import IngestionService
from codefixer.domain.tasks import IngestedTicket
from codefixer.infrastructure.database import connect_database, initialize_database
from codefixer.infrastructure.task_store import TaskStore


def test_routing_failure_recovers_on_same_long_lived_task(tmp_path: Path):
    db_path = initialize_database(tmp_path)
    ticket = IngestedTicket("tapd", "100", "Bug", {"module": "商城", "createdAt": "2026-08-12T00:00:00Z"}, "v1")
    with connect_database(db_path) as db:
        first = IngestionService(db, [], "awaitingStart").ingest_batch("tapd", TicketBatch([ticket], "v1", 1))
        task_id = str(first["taskIds"][0])
        failed = TaskStore(db).get_task(task_id)
        assert failed["status"] == "failed"
        assert failed["project_id"] is None
        assert failed["failure"]["code"] == "project_not_found"
        projects = [{"id": "shop", "intakeStartedAt": "2026-08-11T00:00:00Z", "routingRules": [{"providerRef": "tapd", "priority": 10, "catchAll": True}]}]
        second = IngestionService(db, projects, "awaitingStart").ingest_batch("tapd", TicketBatch([ticket], "v1", 1))
        assert second["taskIds"] == [task_id]
        recovered = TaskStore(db).get_task(task_id)
        assert recovered["status"] == "awaiting_start"
        assert recovered["project_id"] == "shop"
        assert db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 1


def test_ticket_before_pipeline_intake_is_not_persisted_as_task(tmp_path: Path):
    db_path = initialize_database(tmp_path)
    ticket = IngestedTicket("tapd", "old", "Old Bug", {"createdAt": "2026-08-10T00:00:00Z"}, "v1")
    projects = [{"id": "shop", "intakeStartedAt": "2026-08-11T00:00:00Z", "routingRules": [{"providerRef": "tapd", "priority": 10, "catchAll": True}]}]
    with connect_database(db_path) as db:
        result = IngestionService(db, projects, "awaitingStart").ingest_batch("tapd", TicketBatch([ticket], "v1", 1))
        assert result["ingested"] == 0
        assert result["taskIds"] == []
        assert db.execute("SELECT COUNT(*) FROM tasks").fetchone()[0] == 0
