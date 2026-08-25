from uuid import UUID

from app.domain.enums import EventName
from app.domain.models import Event, Journey, Patient, ProtocolSession, Task
from app.repositories.in_memory import (
    EventRepository,
    JourneyRepository,
    PatientRepository,
    ProtocolRepository,
)

PATIENT_ID = UUID("00000000-0000-0000-0000-000000000001")


def make_patient() -> Patient:
    return Patient(
        patient_id=PATIENT_ID,
        patient_id_hash="patient-id-hash",
        phone="+5511999999999",
        phone_hash="patient-hash",
        name="Test Patient",
        birth_date="1990-01-01",
        sex="F",
    )


def make_session() -> ProtocolSession:
    return ProtocolSession(
        patient_id=PATIENT_ID,
        template_id="phq9",
        template_version="1",
        current_question_id="q1",
    )


def make_journey() -> Journey:
    return Journey(
        patient_id=PATIENT_ID,
        objective="Acompanhamento de saúde",
        tasks=[Task(title="Realizar primeiro check-in")],
    )


def make_event() -> Event:
    return Event(
        event_name=EventName.PATIENT_CREATED,
        patient_id_hash="patient-hash",
    )


def test_patient_repository_saves_and_gets_patient() -> None:
    repository = PatientRepository()
    patient = make_patient()

    repository.save(patient)

    assert repository.get(patient.patient_id) == patient


def test_patient_repository_returns_none_for_unknown_patient() -> None:
    repository = PatientRepository()

    assert repository.get(PATIENT_ID) is None


def test_protocol_repository_saves_and_gets_session() -> None:
    repository = ProtocolRepository()
    session = make_session()

    repository.save(session)

    assert repository.get(session.session_id) == session


def test_protocol_repository_replaces_existing_session() -> None:
    repository = ProtocolRepository()
    session = make_session()
    repository.save(session)
    session.current_question_id = "q2"

    repository.save(session)

    assert repository.get(session.session_id) == session
    assert repository.get(session.session_id).current_question_id == "q2"


def test_journey_repository_saves_gets_and_finds_by_patient() -> None:
    repository = JourneyRepository()
    journey = make_journey()

    repository.save(journey)

    assert repository.get(journey.journey_id) == journey
    assert repository.get_by_patient(PATIENT_ID) == journey


def test_journey_repository_returns_none_when_not_found() -> None:
    repository = JourneyRepository()

    assert repository.get(PATIENT_ID) is None
    assert repository.get_by_patient(PATIENT_ID) is None


def test_event_repository_appends_and_lists_events_by_patient() -> None:
    repository = EventRepository()
    first = make_event()
    second = Event(event_name=EventName.TERMS_ACCEPTED, patient_id_hash="other-hash")

    repository.append(first)
    repository.append(second)

    assert repository.list_by_patient("patient-hash") == [first]
    assert repository.list_all() == [first, second]


def test_event_repository_does_not_expose_mutable_internal_list() -> None:
    repository = EventRepository()
    event = make_event()
    repository.append(event)

    events = repository.list_all()
    events.clear()

    assert repository.list_all() == [event]
