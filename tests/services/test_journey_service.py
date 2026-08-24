from uuid import UUID, uuid4

import pytest

from app.domain.enums import EventName, JourneyStatus, ProtocolSessionStatus, TaskStatus
from app.domain.errors import (
    JourneyNotFound,
    ProtocolNotCompleted,
    TaskAlreadyCompleted,
    TaskNotFound,
)
from app.domain.models import ProtocolSession
from app.repositories.in_memory import EventRepository, JourneyRepository
from app.services.event_service import EventService
from app.services.journey_service import JourneyService

PATIENT_ID = UUID("00000000-0000-0000-0000-000000000001")
PATIENT_ID_HASH = "patient-hash"


def make_service() -> tuple[JourneyService, JourneyRepository, EventRepository]:
    journey_repository = JourneyRepository()
    event_repository = EventRepository()
    return (
        JourneyService(journey_repository, EventService(event_repository)),
        journey_repository,
        event_repository,
    )


def make_session(status: ProtocolSessionStatus) -> ProtocolSession:
    return ProtocolSession(
        patient_id=PATIENT_ID,
        template_id="phq9",
        template_version="1.0",
        status=status,
        current_question_id=None,
        score=2 if status == ProtocolSessionStatus.COMPLETED else None,
        ended_by_skip=True if status == ProtocolSessionStatus.COMPLETED else None,
    )


def test_completed_protocol_creates_and_persists_expected_journey() -> None:
    service, repository, _ = make_service()

    journey = service.create_journey(
        PATIENT_ID,
        PATIENT_ID_HASH,
        make_session(ProtocolSessionStatus.COMPLETED),
    )

    assert journey.status == JourneyStatus.IN_PROGRESS
    assert journey.objective == "Acompanhamento após protocolo clínico"
    assert len(journey.tasks) == 1
    assert journey.tasks[0].title == "Realizar acompanhamento"
    assert journey.tasks[0].status == TaskStatus.IN_PROGRESS
    assert repository.get(journey.journey_id) == journey


def test_in_progress_protocol_does_not_persist_journey_or_emit_event() -> None:
    service, repository, event_repository = make_service()

    with pytest.raises(ProtocolNotCompleted):
        service.create_journey(
            PATIENT_ID,
            PATIENT_ID_HASH,
            make_session(ProtocolSessionStatus.IN_PROGRESS),
        )

    assert repository.get_by_patient(PATIENT_ID) is None
    assert event_repository.list_all() == []


def test_create_journey_emits_exactly_one_lgpd_safe_event() -> None:
    service, _, event_repository = make_service()

    journey = service.create_journey(
        PATIENT_ID,
        PATIENT_ID_HASH,
        make_session(ProtocolSessionStatus.COMPLETED),
    )

    events = event_repository.list_all()
    assert len(events) == 1
    event = events[0]
    assert event.event_name == EventName.JOURNEY_CREATED
    assert event.patient_id_hash == PATIENT_ID_HASH
    assert event.properties == {
        "journey_id": str(journey.journey_id),
        "objective": "Acompanhamento após protocolo clínico",
    }
    serialized = event.model_dump_json()
    assert "phone" not in serialized
    assert "birth_date" not in serialized
    assert '"name"' not in serialized


def test_complete_task_changes_status_persists_and_emits_event() -> None:
    service, repository, event_repository = make_service()
    journey = service.create_journey(
        PATIENT_ID,
        PATIENT_ID_HASH,
        make_session(ProtocolSessionStatus.COMPLETED),
    )
    event_repository._events.clear()
    task = journey.tasks[0]

    result = service.complete_task(journey.journey_id, task.task_id, PATIENT_ID_HASH)

    assert result.status == TaskStatus.COMPLETED
    persisted = repository.get(journey.journey_id)
    assert persisted is not None
    assert persisted.tasks[0].status == TaskStatus.COMPLETED
    assert persisted.status == JourneyStatus.IN_PROGRESS
    assert not any(item.status == TaskStatus.IN_PROGRESS for item in persisted.tasks)
    events = event_repository.list_all()
    assert len(events) == 1
    assert events[0].event_name == EventName.TASK_COMPLETED
    assert events[0].properties == {
        "journey_id": str(journey.journey_id),
        "task_id": str(task.task_id),
    }


def test_missing_journey_raises_without_event() -> None:
    service, _, event_repository = make_service()

    with pytest.raises(JourneyNotFound):
        service.complete_task(uuid4(), uuid4(), PATIENT_ID_HASH)

    assert event_repository.list_all() == []


def test_missing_task_raises_without_additional_event() -> None:
    service, _, event_repository = make_service()
    journey = service.create_journey(
        PATIENT_ID,
        PATIENT_ID_HASH,
        make_session(ProtocolSessionStatus.COMPLETED),
    )
    before = list(event_repository.list_all())

    with pytest.raises(TaskNotFound):
        service.complete_task(journey.journey_id, uuid4(), PATIENT_ID_HASH)

    assert event_repository.list_all() == before
    assert journey.tasks[0].status == TaskStatus.IN_PROGRESS


def test_already_completed_task_raises_and_does_not_emit_second_event() -> None:
    service, _, event_repository = make_service()
    journey = service.create_journey(
        PATIENT_ID,
        PATIENT_ID_HASH,
        make_session(ProtocolSessionStatus.COMPLETED),
    )
    task = journey.tasks[0]
    service.complete_task(journey.journey_id, task.task_id, PATIENT_ID_HASH)
    event_count = len(event_repository.list_all())

    with pytest.raises(TaskAlreadyCompleted):
        service.complete_task(journey.journey_id, task.task_id, PATIENT_ID_HASH)

    assert len(event_repository.list_all()) == event_count
