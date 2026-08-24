from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def _patient_payload(*, consent: bool = True) -> dict[str, object]:
    suffix = str(uuid4().int)[-10:]
    return {
        "phone": f"+55 11 9{suffix}",
        "name": "Adversarial Patient",
        "birth_date": "1990-01-01",
        "sex": "F",
        "terms_accepted": consent,
    }


def _create_patient(*, consent: bool = True) -> tuple[dict[str, object], dict[str, object]]:
    payload = _patient_payload(consent=consent)
    response = client.post("/patients", json=payload)
    assert response.status_code == 201
    return payload, response.json()


def _start(patient_id: str, template_id: str = "phq9"):
    return client.post(
        f"/patients/{patient_id}/protocols",
        json={"template_id": template_id},
    )


def _answer(session_id: str, question_id: str, value: int):
    return client.post(
        f"/protocol-sessions/{session_id}/answers",
        json={"question_id": question_id, "value": value},
    )


def _events(patient_id: str) -> list[dict[str, object]]:
    response = client.get("/events", params={"patient_id": patient_id})
    assert response.status_code == 200
    return response.json()


def _assert_no_pii(response_text: str, payload: dict[str, object]) -> None:
    assert str(payload["phone"]) not in response_text
    assert str(payload["name"]) not in response_text
    assert str(payload["birth_date"]) not in response_text


def test_existing_patient_without_journey_returns_404() -> None:
    payload, patient = _create_patient()

    response = client.get(f"/patients/{patient['patient_id']}/journey")

    assert response.status_code == 404
    assert response.json()["error"] == "journey_not_found"
    _assert_no_pii(response.text, payload)


def test_journey_does_not_exist_after_only_first_answer() -> None:
    payload, patient = _create_patient()
    session_id = _start(patient["patient_id"]).json()["session_id"]

    first = _answer(session_id, "1", 1)
    journey = client.get(f"/patients/{patient['patient_id']}/journey")

    assert first.status_code == 200
    assert first.json()["status"] == "in_progress"
    assert journey.status_code == 404
    assert journey.json()["error"] == "journey_not_found"
    _assert_no_pii(journey.text, payload)


def test_missing_template_is_404_without_protocol_started_event() -> None:
    payload, patient = _create_patient()

    response = _start(patient["patient_id"], template_id="does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"] == "protocol_template_not_found"
    names = [event["event_name"] for event in _events(patient["patient_id"])]
    assert "protocol_started" not in names
    _assert_no_pii(response.text, payload)


def test_missing_session_is_404_and_malformed_uuid_is_sanitized_422() -> None:
    missing = _answer(str(uuid4()), "1", 1)
    malformed = client.get("/patients/not-a-uuid/journey")

    assert missing.status_code == 404
    assert missing.json()["error"] == "protocol_session_not_found"
    assert malformed.status_code == 422
    assert malformed.json() == {
        "error": "validation_error",
        "message": "Invalid request",
    }
    assert "not-a-uuid" not in malformed.text


def test_retry_completed_session_is_409_without_duplicate_completion_or_journey_events() -> None:
    payload, patient = _create_patient()
    session_id = _start(patient["patient_id"]).json()["session_id"]
    _answer(session_id, "1", 1)
    completed = _answer(session_id, "2", 1)

    retry = _answer(session_id, "2", 1)

    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"
    assert retry.status_code == 409
    assert retry.json()["error"] == "protocol_already_completed"
    names = [event["event_name"] for event in _events(patient["patient_id"])]
    assert names.count("protocol_completed") == 1
    assert names.count("journey_created") == 1
    _assert_no_pii(retry.text, payload)


def test_followup_rule_precedence_for_missing_consent_and_incomplete_protocol() -> None:
    _, no_consent_patient = _create_patient(consent=False)
    missing_consent = client.post(
        "/followups/evaluate",
        json={"patient_id": no_consent_patient["patient_id"]},
    )
    assert missing_consent.status_code == 200
    assert missing_consent.json()["eligible"] is False
    assert missing_consent.json()["reason"] == "missing_consent"

    _, incomplete_patient = _create_patient(consent=True)
    _start(incomplete_patient["patient_id"])
    incomplete = client.post(
        "/followups/evaluate",
        json={"patient_id": incomplete_patient["patient_id"]},
    )
    assert incomplete.status_code == 200
    assert incomplete.json()["eligible"] is False
    assert incomplete.json()["reason"] == "protocol_not_completed"


def test_missing_task_is_404_without_task_completed_event() -> None:
    payload, patient = _create_patient()
    session_id = _start(patient["patient_id"]).json()["session_id"]
    _answer(session_id, "1", 1)
    _answer(session_id, "2", 1)
    journey = client.get(f"/patients/{patient['patient_id']}/journey").json()

    response = client.post(
        f"/journeys/{journey['journey_id']}/tasks/{uuid4()}/complete"
    )

    assert response.status_code == 404
    assert response.json()["error"] == "task_not_found"
    names = [event["event_name"] for event in _events(patient["patient_id"])]
    assert "task_completed" not in names
    _assert_no_pii(response.text, payload)


def test_acceptance_flow_with_completed_task_skips_followup_without_pii() -> None:
    payload, patient = _create_patient()
    session_id = _start(patient["patient_id"]).json()["session_id"]
    _answer(session_id, "1", 1)
    _answer(session_id, "2", 1)

    journey_response = client.get(f"/patients/{patient['patient_id']}/journey")
    assert journey_response.status_code == 200
    journey = journey_response.json()
    assert journey["status"] == "em_andamento"
    task = journey["tasks"][0]

    completed = client.post(
        f"/journeys/{journey['journey_id']}/tasks/{task['task_id']}/complete"
    )
    assert completed.status_code == 200
    assert completed.json()["status"] == "completed"

    followup = client.post(
        "/followups/evaluate",
        json={"patient_id": patient["patient_id"]},
    )
    assert followup.status_code == 200
    assert followup.json() == {
        "eligible": False,
        "template_key": None,
        "reason": "no_active_task",
    }

    events_response = client.get("/events", params={"patient_id": patient["patient_id"]})
    assert events_response.status_code == 200
    events = events_response.json()
    names = [event["event_name"] for event in events]
    assert names.count("task_completed") == 1
    assert names[-1] == "followup_skipped"
    assert events[-1]["properties"] == {"reason": "no_active_task"}
    assert names == [
        "patient_created",
        "terms_accepted",
        "protocol_started",
        "protocol_completed",
        "journey_created",
        "task_completed",
        "followup_skipped",
    ]
    _assert_no_pii(events_response.text, payload)
    for event in events:
        assert "phone" not in event["properties"]
        assert "name" not in event["properties"]
        assert "birth_date" not in event["properties"]
