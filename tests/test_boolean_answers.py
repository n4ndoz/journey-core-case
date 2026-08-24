from datetime import date

import pytest
from fastapi.testclient import TestClient

from app.domain.enums import EventName
from app.domain.errors import InvalidAnswer
from app.domain.models import Patient, ProtocolAnswer
from app.main import app
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

client = TestClient(app)


def _make_service() -> tuple[
    ProtocolService,
    PatientRepository,
    JourneyRepository,
    EventRepository,
]:
    patients = PatientRepository()
    protocols = ProtocolRepository()
    journeys = JourneyRepository()
    events = EventRepository()
    event_service = EventService(events)
    return (
        ProtocolService(
            patients,
            protocols,
            TemplateLoader(),
            ProtocolEngine(),
            event_service,
            JourneyService(journeys, event_service),
        ),
        patients,
        journeys,
        events,
    )


def test_internal_boolean_answer_is_rejected_atomically_and_session_recovers() -> None:
    service, patients, journeys, events = _make_service()
    patient = Patient(
        patient_id_hash="patient-id-hash",
        phone="5511999999999",
        phone_hash="phone-hash",
        name="Patient",
        birth_date=date(1990, 1, 1),
        sex="F",
        terms_accepted=True,
    )
    patients.save(patient)
    session = service.start_protocol(patient.patient_id, "phq9")
    events_before = len(events.list_all())

    boolean_answer = ProtocolAnswer.model_construct(question_id="1", value=True)
    with pytest.raises(InvalidAnswer):
        service.submit_answer(session.session_id, boolean_answer)

    assert session.answers == []
    assert session.current_question_id == "1"
    assert journeys.get_by_patient(patient.patient_id) is None
    assert len(events.list_all()) == events_before
    assert not any(
        event.event_name == EventName.PROTOCOL_COMPLETED for event in events.list_all()
    )

    result = service.submit_answer(
        session.session_id,
        ProtocolAnswer(question_id="1", value=1),
    )
    assert result.current_question_id == "2"
    assert [answer.value for answer in result.answers] == [1]


def test_http_boolean_answer_returns_sanitized_422_and_valid_retry_continues() -> None:
    phone = "+55 11 98888-7766"
    name = "Sensitive Bool Patient"
    patient_response = client.post(
        "/patients",
        json={
            "phone": phone,
            "name": name,
            "birth_date": "1985-05-20",
            "sex": "F",
            "terms_accepted": True,
        },
    )
    assert patient_response.status_code == 201
    patient_id = patient_response.json()["patient_id"]
    started = client.post(
        f"/patients/{patient_id}/protocols",
        json={"template_id": "phq9"},
    )
    session_id = started.json()["session_id"]

    invalid = client.post(
        f"/protocol-sessions/{session_id}/answers",
        json={"question_id": "1", "value": True},
    )
    assert invalid.status_code == 422
    assert invalid.json() == {
        "error": "validation_error",
        "message": "Invalid request",
    }
    assert phone not in invalid.text
    assert name not in invalid.text
    assert "1985-05-20" not in invalid.text

    valid = client.post(
        f"/protocol-sessions/{session_id}/answers",
        json={"question_id": "1", "value": 1},
    )
    assert valid.status_code == 200
    assert valid.json()["next_question"]["id"] == "2"
