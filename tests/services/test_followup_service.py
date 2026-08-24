from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest

from app.domain.enums import (
    EventName,
    FollowupSkipReason,
    JourneyStatus,
    ProtocolSessionStatus,
    TaskStatus,
)
from app.domain.errors import PatientNotFound
from app.domain.models import Event, Journey, Patient, ProtocolSession, Task
from app.followups.engine import FollowupEngine
from app.followups.loader import FollowupRulesLoader
from app.repositories.in_memory import (
    EventRepository,
    JourneyRepository,
    PatientRepository,
    ProtocolRepository,
)
from app.services.event_service import EventService
from app.services.followup_service import FollowupService

NOW = datetime(2026, 1, 10, 12, 0, tzinfo=timezone.utc)


def make_service() -> tuple[
    FollowupService,
    PatientRepository,
    ProtocolRepository,
    JourneyRepository,
    EventRepository,
]:
    patient_repository = PatientRepository()
    protocol_repository = ProtocolRepository()
    journey_repository = JourneyRepository()
    event_repository = EventRepository()
    return (
        FollowupService(
            patient_repository,
            protocol_repository,
            journey_repository,
            event_repository,
            FollowupRulesLoader(),
            FollowupEngine(),
            EventService(event_repository),
        ),
        patient_repository,
        protocol_repository,
        journey_repository,
        event_repository,
    )


def save_patient(repository: PatientRepository, *, consent: bool = True) -> Patient:
    patient = Patient(
        phone="5511999999999",
        phone_hash="patient-hash",
        name="Patient",
        birth_date=date(1990, 1, 1),
        sex="F",
        terms_accepted=consent,
    )
    repository.save(patient)
    return patient


def save_completed_protocol(repository: ProtocolRepository, patient: Patient) -> None:
    repository.save(
        ProtocolSession(
            patient_id=patient.patient_id,
            template_id="generic_protocol",
            template_version="1.0",
            status=ProtocolSessionStatus.COMPLETED,
            current_question_id=None,
            score=1,
            ended_by_skip=False,
        )
    )


def save_active_journey(repository: JourneyRepository, patient: Patient, *, active_task: bool = True) -> Journey:
    journey = Journey(
        patient_id=patient.patient_id,
        status=JourneyStatus.IN_PROGRESS,
        objective="Acompanhamento",
        tasks=[
            Task(
                title="Realizar acompanhamento",
                status=TaskStatus.IN_PROGRESS if active_task else TaskStatus.COMPLETED,
            )
        ],
    )
    repository.save(journey)
    return journey


def make_eligible_state() -> tuple[FollowupService, Patient, EventRepository]:
    service, patients, protocols, journeys, events = make_service()
    patient = save_patient(patients)
    save_completed_protocol(protocols, patient)
    save_active_journey(journeys, patient)
    return service, patient, events


def test_valid_context_is_eligible_and_emits_configured_template_key() -> None:
    service, patient, event_repository = make_eligible_state()

    decision = service.evaluate(patient.patient_id, evaluated_at=NOW)

    assert decision.eligible is True
    assert decision.template_key == "checkin_adesao"
    assert decision.reason is None
    events = event_repository.list_all()
    assert len(events) == 1
    assert events[0].event_name == EventName.FOLLOWUP_ELIGIBLE
    assert events[0].properties == {"template_key": "checkin_adesao"}


@pytest.mark.parametrize(
    ("state", "reason"),
    [
        ("missing_consent", FollowupSkipReason.MISSING_CONSENT),
        ("protocol_not_completed", FollowupSkipReason.PROTOCOL_NOT_COMPLETED),
        ("journey_not_active", FollowupSkipReason.JOURNEY_NOT_ACTIVE),
        ("no_active_task", FollowupSkipReason.NO_ACTIVE_TASK),
    ],
)
def test_ineligible_states_emit_exactly_one_typed_skip(state: str, reason: FollowupSkipReason) -> None:
    service, patients, protocols, journeys, event_repository = make_service()
    patient = save_patient(patients, consent=state != "missing_consent")
    if state != "protocol_not_completed":
        save_completed_protocol(protocols, patient)
    if state not in {"journey_not_active", "protocol_not_completed"}:
        save_active_journey(journeys, patient, active_task=state != "no_active_task")

    decision = service.evaluate(patient.patient_id, evaluated_at=NOW)

    assert decision.eligible is False
    assert decision.reason == reason
    events = event_repository.list_all()
    assert len(events) == 1
    assert events[0].event_name == EventName.FOLLOWUP_SKIPPED
    assert events[0].properties == {"reason": reason.value}


def test_first_eligible_then_immediate_second_evaluation_is_cooldown() -> None:
    service, patient, event_repository = make_eligible_state()

    first = service.evaluate(patient.patient_id)
    second = service.evaluate(patient.patient_id)

    assert first.eligible is True
    assert second.eligible is False
    assert second.reason == FollowupSkipReason.COOLDOWN
    names = [event.event_name for event in event_repository.list_all()]
    assert names == [EventName.FOLLOWUP_ELIGIBLE, EventName.FOLLOWUP_SKIPPED]


def test_cooldown_boundary_at_exactly_72_hours_is_eligible() -> None:
    service, patient, event_repository = make_eligible_state()
    event_repository.append(
        Event(
            occurred_at=NOW - timedelta(hours=72),
            event_name=EventName.FOLLOWUP_ELIGIBLE,
            patient_id_hash=patient.phone_hash,
            properties={"template_key": "checkin_adesao"},
        )
    )

    decision = service.evaluate(patient.patient_id, evaluated_at=NOW)

    assert decision.eligible is True
    assert [event.event_name for event in event_repository.list_all()] == [
        EventName.FOLLOWUP_ELIGIBLE,
        EventName.FOLLOWUP_ELIGIBLE,
    ]


def test_recent_followup_produces_cooldown_skip() -> None:
    service, patient, event_repository = make_eligible_state()
    event_repository.append(
        Event(
            occurred_at=NOW - timedelta(hours=71, minutes=59, seconds=59),
            event_name=EventName.FOLLOWUP_ELIGIBLE,
            patient_id_hash=patient.phone_hash,
            properties={"template_key": "checkin_adesao"},
        )
    )

    decision = service.evaluate(patient.patient_id, evaluated_at=NOW)

    assert decision.reason == FollowupSkipReason.COOLDOWN
    assert event_repository.list_all()[-1].event_name == EventName.FOLLOWUP_SKIPPED


def test_missing_patient_raises_without_followup_event() -> None:
    service, _, _, _, event_repository = make_service()

    with pytest.raises(PatientNotFound):
        service.evaluate(uuid4(), evaluated_at=NOW)

    assert event_repository.list_all() == []
