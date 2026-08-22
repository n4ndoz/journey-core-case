from datetime import datetime, timezone
from uuid import UUID

import pytest

from app.domain.event_properties import (
    FollowupEligibleProperties,
    FollowupSkippedProperties,
    JourneyCreatedProperties,
    PatientCreatedProperties,
    ProtocolCompletedProperties,
    ProtocolStartedProperties,
    TaskCompletedProperties,
    TermsAcceptedProperties,
)
from app.domain.enums import EventName, FollowupSkipReason
from app.repositories.in_memory import EventRepository
from app.services.event_service import EventService


PATIENT_HASH = "patient-hash"
JOURNEY_ID = UUID("00000000-0000-0000-0000-000000000001")
TASK_ID = UUID("00000000-0000-0000-0000-000000000002")


@pytest.fixture
def event_service() -> EventService:
    return EventService(EventRepository())


@pytest.mark.parametrize(
    ("event_name", "properties"),
    [
        (EventName.PATIENT_CREATED, PatientCreatedProperties()),
        (EventName.TERMS_ACCEPTED, TermsAcceptedProperties()),
        (
            EventName.PROTOCOL_STARTED,
            ProtocolStartedProperties(template_id="phq9", template_version="1"),
        ),
        (
            EventName.PROTOCOL_COMPLETED,
            ProtocolCompletedProperties(
                template_id="phq9",
                template_version="1",
                score=2,
                ended_by_skip=True,
            ),
        ),
        (
            EventName.JOURNEY_CREATED,
            JourneyCreatedProperties(journey_id=JOURNEY_ID, objective="Acompanhamento de saúde"),
        ),
        (
            EventName.TASK_COMPLETED,
            TaskCompletedProperties(journey_id=JOURNEY_ID, task_id=TASK_ID),
        ),
        (
            EventName.FOLLOWUP_ELIGIBLE,
            FollowupEligibleProperties(template_key="checkin_adesao"),
        ),
        (
            EventName.FOLLOWUP_SKIPPED,
            FollowupSkippedProperties(reason=FollowupSkipReason.COOLDOWN),
        ),
    ],
)
def test_emit_persists_typed_event_properties(
    event_service: EventService,
    event_name: EventName,
    properties: object,
) -> None:
    event = event_service.emit(event_name, PATIENT_HASH, properties)  # type: ignore[arg-type]

    assert event.event_id is not None
    assert event.event_name == event_name
    assert event.patient_id_hash == PATIENT_HASH
    assert event.properties == properties.model_dump(mode="json")
    assert event.occurred_at.tzinfo is not None
    assert event.occurred_at.utcoffset() == timezone.utc.utcoffset(event.occurred_at)


def test_emit_persists_through_event_repository() -> None:
    repository = EventRepository()
    service = EventService(repository)

    event = service.emit(EventName.PATIENT_CREATED, PATIENT_HASH, PatientCreatedProperties())

    assert repository.list_all() == [event]


def test_emit_rejects_untyped_properties(event_service: EventService) -> None:
    with pytest.raises(TypeError):
        event_service.emit(EventName.PATIENT_CREATED, PATIENT_HASH, {"phone": "123"})  # type: ignore[arg-type]


def test_event_property_schema_forbids_extra_fields() -> None:
    with pytest.raises(ValueError):
        PatientCreatedProperties(phone="+5521999999999")


def test_followup_skip_reason_is_typed() -> None:
    properties = FollowupSkippedProperties(reason=FollowupSkipReason.COOLDOWN)

    assert properties.reason is FollowupSkipReason.COOLDOWN


def test_event_service_has_no_update_or_delete_operations() -> None:
    service = EventService(EventRepository())

    assert not hasattr(service, "update")
    assert not hasattr(service, "delete")
