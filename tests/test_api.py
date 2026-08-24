from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def patient_payload(*, consent: bool = True) -> dict[str, object]:
    suffix = str(uuid4().int)[-10:]
    return {
        "phone": f"+55 11 9{suffix}",
        "name": "Paciente Teste",
        "birth_date": "1990-01-01",
        "sex": "F",
        "terms_accepted": consent,
    }


def create_patient(*, consent: bool = True) -> tuple[dict[str, object], dict[str, object]]:
    payload = patient_payload(consent=consent)
    response = client.post("/patients", json=payload)
    assert response.status_code == 201
    return payload, response.json()


def start_phq9(patient_id: str):
    return client.post(
        f"/patients/{patient_id}/protocols",
        json={"template_id": "phq9"},
    )


def answer(session_id: str, question_id: str, value: int):
    return client.post(
        f"/protocol-sessions/{session_id}/answers",
        json={"question_id": question_id, "value": value},
    )


def test_health_and_patient_creation_response_contract() -> None:
    assert client.get("/health").json() == {"status": "ok"}

    payload, body = create_patient()

    assert body["name"] == payload["name"]
    assert body["birth_date"] == payload["birth_date"]
    assert body["sex"] == payload["sex"]
    assert body["terms_accepted"] is True
    assert "patient_id" in body
    assert "phone_hash" not in body


def test_protocol_start_returns_prompt_and_first_question() -> None:
    _, patient = create_patient()

    response = start_phq9(patient["patient_id"])

    assert response.status_code == 201
    body = response.json()
    assert body["status"] == "in_progress"
    assert body["current_question"]["id"] == "1"
    assert body["current_question"]["type"] == "likert"
    assert body["current_question"]["options"][0] == {
        "value": 0,
        "label": "Nenhuma vez",
    }
    assert body["prompt"] == "Nas últimas duas semanas, com que frequência você foi incomodado por…"


def test_protocol_start_errors_are_typed_and_do_not_expose_pii() -> None:
    payload, patient = create_patient(consent=False)

    response = start_phq9(patient["patient_id"])

    assert response.status_code == 403
    assert response.json()["error"] == "consent_required"
    serialized = response.text
    assert payload["phone"] not in serialized
    assert payload["name"] not in serialized
    assert payload["birth_date"] not in serialized

    missing = start_phq9(str(uuid4()))
    assert missing.status_code == 404
    assert missing.json()["error"] == "patient_not_found"


def test_answer_validation_skip_and_boundary() -> None:
    _, patient = create_patient()
    started = start_phq9(patient["patient_id"]).json()
    session_id = started["session_id"]

    out_of_order = answer(session_id, "2", 1)
    assert out_of_order.status_code == 409
    assert out_of_order.json()["error"] == "question_mismatch"

    invalid = answer(session_id, "1", 99)
    assert invalid.status_code == 422
    assert invalid.json()["error"] == "invalid_answer"

    assert answer(session_id, "1", 1).json()["next_question"]["id"] == "2"
    skipped = answer(session_id, "2", 1)
    assert skipped.status_code == 200
    assert skipped.json() == {
        "session_id": session_id,
        "status": "completed",
        "next_question": None,
        "score": 2,
        "ended_by_skip": True,
    }

    _, boundary_patient = create_patient()
    boundary_session = start_phq9(boundary_patient["patient_id"]).json()["session_id"]
    answer(boundary_session, "1", 2)
    boundary = answer(boundary_session, "2", 1)
    assert boundary.status_code == 200
    assert boundary.json()["status"] == "in_progress"
    assert boundary.json()["next_question"]["id"] == "3"


def test_full_phq9_completion() -> None:
    _, patient = create_patient()
    session_id = start_phq9(patient["patient_id"]).json()["session_id"]

    values = [2, 1, 1, 1, 1, 1, 1, 1, 1]
    final = None
    for question_id, value in enumerate(values, start=1):
        final = answer(session_id, str(question_id), value)
        assert final.status_code == 200

    body = final.json()
    assert body["status"] == "completed"
    assert body["score"] == 10
    assert body["ended_by_skip"] is False
    assert body["next_question"] is None


def test_journey_query_and_task_completion() -> None:
    _, patient = create_patient()
    session_id = start_phq9(patient["patient_id"]).json()["session_id"]
    answer(session_id, "1", 1)
    answer(session_id, "2", 1)

    response = client.get(f"/patients/{patient['patient_id']}/journey")
    assert response.status_code == 200
    journey = response.json()
    assert journey["status"] == "in_progress"
    assert journey["objective"] == "Acompanhamento após protocolo clínico"
    assert len(journey["tasks"]) == 1
    task = journey["tasks"][0]
    assert task["title"] == "Realizar acompanhamento"
    assert task["status"] == "in_progress"

    completed = client.post(
        f"/journeys/{journey['journey_id']}/tasks/{task['task_id']}/complete"
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    repeated = client.post(
        f"/journeys/{journey['journey_id']}/tasks/{task['task_id']}/complete"
    )
    assert repeated.status_code == 409
    assert repeated.json()["error"] == "task_already_completed"


def test_followup_cooldown_and_event_trail_are_lgpd_safe() -> None:
    payload, patient = create_patient()
    session_id = start_phq9(patient["patient_id"]).json()["session_id"]
    answer(session_id, "1", 1)
    answer(session_id, "2", 1)

    first = client.post("/followups/evaluate", json={"patient_id": patient["patient_id"]})
    assert first.status_code == 200
    assert first.json() == {
        "eligible": True,
        "template_key": "checkin_adesao",
        "reason": None,
    }

    second = client.post("/followups/evaluate", json={"patient_id": patient["patient_id"]})
    assert second.status_code == 200
    assert second.json() == {
        "eligible": False,
        "template_key": None,
        "reason": "cooldown",
    }

    events_response = client.get("/events", params={"patient_id": patient["patient_id"]})
    assert events_response.status_code == 200
    events = events_response.json()
    names = [event["event_name"] for event in events]
    assert names == [
        "patient_created",
        "terms_accepted",
        "protocol_started",
        "protocol_completed",
        "journey_created",
        "followup_eligible",
        "followup_skipped",
    ]

    serialized = events_response.text
    assert payload["phone"] not in serialized
    assert payload["name"] not in serialized
    assert payload["birth_date"] not in serialized
    for event in events:
        assert "phone" not in event
        assert "name" not in event
        assert "birth_date" not in event
        assert "phone" not in event["properties"]
        assert "name" not in event["properties"]
        assert "birth_date" not in event["properties"]


def test_events_and_journey_for_missing_patient_are_404() -> None:
    patient_id = str(uuid4())

    events = client.get("/events", params={"patient_id": patient_id})
    journey = client.get(f"/patients/{patient_id}/journey")

    assert events.status_code == 404
    assert events.json()["error"] == "patient_not_found"
    assert journey.status_code == 404
    assert journey.json()["error"] == "patient_not_found"


def test_request_validation_error_does_not_echo_phone() -> None:
    phone = "+55 11 98888-7777"
    response = client.post(
        "/patients",
        json={
            "phone": phone,
            "name": "Paciente Inválido",
            "birth_date": "not-a-date",
            "sex": "F",
            "terms_accepted": True,
        },
    )

    assert response.status_code == 422
    assert response.json() == {
        "error": "validation_error",
        "message": "Invalid request",
    }
    assert phone not in response.text
