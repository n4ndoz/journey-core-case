from datetime import date
from uuid import UUID, uuid4

import pytest

from app.domain.enums import EventName, ProtocolSessionStatus
from app.domain.errors import (
    ConsentRequired,
    InvalidAnswer,
    PatientNotFound,
    ProtocolSessionNotFound,
)
from app.domain.models import Patient, ProtocolAnswer
from app.protocols.engine import ProtocolEngine
from app.protocols.loader import TemplateLoader
from app.repositories.in_memory import (
    EventRepository,
    JourneyRepository,
    PatientRepository,
    ProtocolRepository,
)
from app.services.event_service import EventService
from app.services.journey_service import JourneyService
from app.services.protocol_service import ProtocolService


def make_service() -> tuple[
    ProtocolService,
    PatientRepository,
    ProtocolRepository,
    JourneyRepository,
    EventRepository,
]:
    patient_repository = PatientRepository()
    protocol_repository = ProtocolRepository()
    journey_repository = JourneyRepository()
    event_repository = EventRepository()
    event_service = EventService(event_repository)
    return (
        ProtocolService(
            patient_repository,
            protocol_repository,
            TemplateLoader(),
            ProtocolEngine(),
            event_service,
            JourneyService(journey_repository, event_service),
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


def test_start_protocol_persists_session_and_emits_protocol_started() -> None:
    service, patient_repository, protocol_repository, _, event_repository = make_service()
    patient = save_patient(patient_repository)

    session = service.start_protocol(patient.patient_id, "phq9")

    assert session.status == ProtocolSessionStatus.IN_PROGRESS
    assert session.current_question_id == "1"
    assert session.answers == []
    assert session.score is None
    assert session.ended_by_skip is None
    assert protocol_repository.get(session.session_id) == session
    events = event_repository.list_all()
    assert len(events) == 1
    assert events[0].event_name == EventName.PROTOCOL_STARTED
    assert events[0].patient_id_hash == patient.phone_hash
    assert events[0].properties == {"template_id": "phq9", "template_version": "1.0"}


def test_start_protocol_rejects_missing_patient_without_side_effects() -> None:
    service, _, protocol_repository, _, event_repository = make_service()

    with pytest.raises(PatientNotFound):
        service.start_protocol(uuid4(), "phq9")

    assert protocol_repository.list_by_patient(UUID("00000000-0000-0000-0000-000000000001")) == []
    assert event_repository.list_all() == []


def test_start_protocol_requires_consent_without_creating_session_or_event() -> None:
    service, patient_repository, protocol_repository, _, event_repository = make_service()
    patient = save_patient(patient_repository, consent=False)

    with pytest.raises(ConsentRequired):
        service.start_protocol(patient.patient_id, "phq9")

    assert protocol_repository.list_by_patient(patient.patient_id) == []
    assert event_repository.list_all() == []


def test_continue_advances_question_without_completion_event_or_journey() -> None:
    service, patient_repository, protocol_repository, journey_repository, event_repository = make_service()
    patient = save_patient(patient_repository)
    session = service.start_protocol(patient.patient_id, "phq9")
    before_events = len(event_repository.list_all())

    result = service.submit_answer(session.session_id, ProtocolAnswer(question_id="1", value=2))

    assert result.status == ProtocolSessionStatus.IN_PROGRESS
    assert result.current_question_id == "2"
    assert protocol_repository.get(session.session_id) == result
    assert journey_repository.get_by_patient(patient.patient_id) is None
    assert len(event_repository.list_all()) == before_events


def test_phq2_skip_completes_persists_score_emits_once_and_creates_journey() -> None:
    service, patient_repository, protocol_repository, journey_repository, event_repository = make_service()
    patient = save_patient(patient_repository)
    session = service.start_protocol(patient.patient_id, "phq9")
    service.submit_answer(session.session_id, ProtocolAnswer(question_id="1", value=1))

    result = service.submit_answer(session.session_id, ProtocolAnswer(question_id="2", value=1))

    assert result.status == ProtocolSessionStatus.COMPLETED
    assert result.current_question_id is None
    assert result.score == 2
    assert result.ended_by_skip is True
    assert protocol_repository.get(session.session_id) == result
    assert journey_repository.get_by_patient(patient.patient_id) is not None
    completed = [
        event for event in event_repository.list_all()
        if event.event_name == EventName.PROTOCOL_COMPLETED
    ]
    assert len(completed) == 1
    assert completed[0].properties["ended_by_skip"] is True
    assert completed[0].properties["score"] == 2


def test_full_protocol_completion_persists_final_score_and_creates_journey() -> None:
    service, patient_repository, _, journey_repository, event_repository = make_service()
    patient = save_patient(patient_repository)
    session = service.start_protocol(patient.patient_id, "phq9")
    values = [2, 1, 1, 2, 0, 3, 1, 2, 1]

    for index, value in enumerate(values, start=1):
        result = service.submit_answer(
            session.session_id,
            ProtocolAnswer(question_id=str(index), value=value),
        )

    assert result.status == ProtocolSessionStatus.COMPLETED
    assert result.score == sum(values)
    assert result.ended_by_skip is False
    assert journey_repository.get_by_patient(patient.patient_id) is not None
    completed = [
        event for event in event_repository.list_all()
        if event.event_name == EventName.PROTOCOL_COMPLETED
    ]
    assert len(completed) == 1
    assert completed[0].properties["ended_by_skip"] is False


def test_missing_session_raises_without_completion_event() -> None:
    service, _, _, _, event_repository = make_service()

    with pytest.raises(ProtocolSessionNotFound):
        service.submit_answer(uuid4(), ProtocolAnswer(question_id="1", value=1))

    assert not any(
        event.event_name == EventName.PROTOCOL_COMPLETED
        for event in event_repository.list_all()
    )


def test_engine_error_does_not_create_journey_or_emit_completion() -> None:
    service, patient_repository, _, journey_repository, event_repository = make_service()
    patient = save_patient(patient_repository)
    session = service.start_protocol(patient.patient_id, "phq9")
    before_events = len(event_repository.list_all())

    with pytest.raises(InvalidAnswer):
        service.submit_answer(session.session_id, ProtocolAnswer(question_id="1", value=4))

    assert journey_repository.get_by_patient(patient.patient_id) is None
    assert len(event_repository.list_all()) == before_events
