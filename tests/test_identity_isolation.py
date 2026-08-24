from uuid import UUID

from fastapi.testclient import TestClient

from app.dependencies import patient_repository
from app.main import app

client = TestClient(app)

PHONE = "+55 11 98888-7777"
NAME = "Sensitive Test Patient"
BIRTH_DATE = "1985-05-20"


def _create_patient(name: str) -> dict[str, object]:
    response = client.post(
        "/patients",
        json={
            "phone": PHONE,
            "name": name,
            "birth_date": BIRTH_DATE,
            "sex": "F",
            "terms_accepted": True,
        },
    )
    assert response.status_code == 201
    assert "phone_hash" not in response.json()
    assert "patient_id_hash" not in response.json()
    return response.json()


def _complete_by_skip(patient_id: str) -> list[object]:
    responses: list[object] = []
    started = client.post(
        f"/patients/{patient_id}/protocols",
        json={"template_id": "phq9"},
    )
    assert started.status_code == 201
    responses.append(started)
    session_id = started.json()["session_id"]

    first = client.post(
        f"/protocol-sessions/{session_id}/answers",
        json={"question_id": "1", "value": 1},
    )
    second = client.post(
        f"/protocol-sessions/{session_id}/answers",
        json={"question_id": "2", "value": 1},
    )
    assert first.status_code == 200
    assert second.status_code == 200
    assert second.json()["status"] == "completed"
    responses.extend([first, second])
    return responses


def _events(patient_id: str) -> object:
    response = client.get("/events", params={"patient_id": patient_id})
    assert response.status_code == 200
    return response


def _assert_no_pii(text: str, *names: str) -> None:
    assert PHONE not in text
    assert BIRTH_DATE not in text
    for name in names:
        assert name not in text


def test_same_phone_patients_have_isolated_event_identity_and_cooldown() -> None:
    patient_a = _create_patient(NAME)
    patient_b = _create_patient("Sensitive Test Patient B")
    patient_a_model = patient_repository.get(UUID(str(patient_a["patient_id"])))
    patient_b_model = patient_repository.get(UUID(str(patient_b["patient_id"])))
    assert patient_a_model is not None
    assert patient_b_model is not None

    assert patient_a_model.patient_id != patient_b_model.patient_id
    assert patient_a_model.phone_hash == patient_b_model.phone_hash
    assert patient_a_model.patient_id_hash != patient_b_model.patient_id_hash
    assert patient_a_model.patient_id_hash != str(patient_a_model.patient_id)
    assert patient_a_model.patient_id_hash != PHONE
    assert patient_a_model.patient_id_hash != patient_a_model.phone_hash

    protocol_responses_a = _complete_by_skip(str(patient_a["patient_id"]))
    followup_a = client.post(
        "/followups/evaluate",
        json={"patient_id": patient_a["patient_id"]},
    )
    assert followup_a.status_code == 200
    assert followup_a.json()["eligible"] is True

    before_protocol_b = client.post(
        "/followups/evaluate",
        json={"patient_id": patient_b["patient_id"]},
    )
    assert before_protocol_b.status_code == 200
    assert before_protocol_b.json()["reason"] == "protocol_not_completed"

    protocol_responses_b = _complete_by_skip(str(patient_b["patient_id"]))
    followup_b = client.post(
        "/followups/evaluate",
        json={"patient_id": patient_b["patient_id"]},
    )
    assert followup_b.status_code == 200
    assert followup_b.json()["eligible"] is True

    events_a_response = _events(str(patient_a["patient_id"]))
    events_b_response = _events(str(patient_b["patient_id"]))
    events_a = events_a_response.json()
    events_b = events_b_response.json()

    assert events_a
    assert events_b
    assert {event["patient_id_hash"] for event in events_a} == {
        patient_a_model.patient_id_hash
    }
    assert {event["patient_id_hash"] for event in events_b} == {
        patient_b_model.patient_id_hash
    }
    assert {event["event_id"] for event in events_a}.isdisjoint(
        {event["event_id"] for event in events_b}
    )
    assert [event["event_name"] for event in events_a].count("followup_eligible") == 1
    assert [event["event_name"] for event in events_b].count("followup_eligible") == 1

    hash_as_patient_id = client.get(
        "/events",
        params={"patient_id": patient_a_model.patient_id_hash},
    )
    assert hash_as_patient_id.status_code == 422
    assert hash_as_patient_id.json() == {
        "error": "validation_error",
        "message": "Invalid request",
    }

    retry_a = client.post(
        f"/protocol-sessions/{protocol_responses_a[-1].json()['session_id']}/answers",
        json={"question_id": "2", "value": 1},
    )
    assert retry_a.status_code == 409

    for response in [
        *protocol_responses_a,
        *protocol_responses_b,
        followup_a,
        before_protocol_b,
        followup_b,
        events_a_response,
        events_b_response,
        hash_as_patient_id,
        retry_a,
    ]:
        _assert_no_pii(response.text, NAME, "Sensitive Test Patient B")
