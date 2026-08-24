from uuid import uuid4

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


def test_complete_http_acceptance_flow() -> None:
    patient_response = client.post(
        "/patients",
        json={
            "phone": f"+55 11 9{str(uuid4().int)[-10:]}",
            "name": "Acceptance Patient",
            "birth_date": "1990-01-01",
            "sex": "F",
            "terms_accepted": True,
        },
    )
    assert patient_response.status_code == 201
    patient_id = patient_response.json()["patient_id"]

    protocol_response = client.post(
        f"/patients/{patient_id}/protocols",
        json={"template_id": "phq9"},
    )
    assert protocol_response.status_code == 201
    session_id = protocol_response.json()["session_id"]

    first_answer = client.post(
        f"/protocol-sessions/{session_id}/answers",
        json={"question_id": "1", "value": 1},
    )
    assert first_answer.status_code == 200
    assert first_answer.json()["next_question"]["id"] == "2"

    completion = client.post(
        f"/protocol-sessions/{session_id}/answers",
        json={"question_id": "2", "value": 1},
    )
    assert completion.status_code == 200
    assert completion.json()["status"] == "completed"
    assert completion.json()["ended_by_skip"] is True

    journey_response = client.get(f"/patients/{patient_id}/journey")
    assert journey_response.status_code == 200
    journey = journey_response.json()
    assert journey["status"] == "in_progress"
    assert len(journey["tasks"]) == 1
    assert journey["tasks"][0]["status"] == "in_progress"

    first_followup = client.post(
        "/followups/evaluate",
        json={"patient_id": patient_id},
    )
    assert first_followup.status_code == 200
    assert first_followup.json()["eligible"] is True

    second_followup = client.post(
        "/followups/evaluate",
        json={"patient_id": patient_id},
    )
    assert second_followup.status_code == 200
    assert second_followup.json()["eligible"] is False
    assert second_followup.json()["reason"] == "cooldown"

    events_response = client.get("/events", params={"patient_id": patient_id})
    assert events_response.status_code == 200
    assert [event["event_name"] for event in events_response.json()] == [
        "patient_created",
        "terms_accepted",
        "protocol_started",
        "protocol_completed",
        "journey_created",
        "followup_eligible",
        "followup_skipped",
    ]
