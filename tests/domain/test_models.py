from datetime import date, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.domain.enums import EventName, JourneyStatus, ProtocolSessionStatus, TaskStatus
from app.domain.models import (
    Event,
    Journey,
    Patient,
    ProtocolAnswer,
    ProtocolSession,
    ProtocolTemplate,
    Question,
    QuestionOption,
    SkipRule,
    SkipRuleCondition,
    SkipRuleTrigger,
    Task,
)


def test_patient_has_internal_id_and_consent_default() -> None:
    patient = Patient(
        patient_id_hash="patient-id-hash",
        phone="+5511999999999",
        phone_hash="hash",
        name="Test Patient",
        birth_date=date(1990, 1, 1),
        sex="F",
    )

    assert isinstance(patient.patient_id, UUID)
    assert patient.terms_accepted is False


def test_patient_requires_patient_id_hash() -> None:
    with pytest.raises(ValidationError):
        Patient(
            phone="+5511999999999",
            phone_hash="hash",
            name="Test Patient",
            birth_date=date(1990, 1, 1),
            sex="F",
        )


def test_patient_rejects_empty_patient_id_hash() -> None:
    with pytest.raises(ValidationError):
        Patient(
            patient_id_hash="",
            phone="+5511999999999",
            phone_hash="hash",
            name="Test Patient",
            birth_date=date(1990, 1, 1),
            sex="F",
        )


def test_protocol_template_contains_questions_and_skip_rules() -> None:
    options = [
        QuestionOption(value=0, label="Nenhuma vez"),
        QuestionOption(value=1, label="Vários dias"),
    ]
    questions = [
        Question(id="q1", text="Question 1", type="likert", options=options),
        Question(id="q2", text="Question 2", type="likert", options=options),
    ]
    rule = SkipRule(
        trigger=SkipRuleTrigger(after_question="q2"),
        condition=SkipRuleCondition(
            operator="sum",
            questions=["q1", "q2"],
            comparison="lt",
            value=3,
        ),
        action="end_block",
    )

    template = ProtocolTemplate(
        template_id="phq9",
        version="1",
        name="PHQ-9",
        questions=questions,
        skip_rules=[rule],
    )

    assert template.questions[0].id == "q1"
    assert template.questions[0].options[0].value == 0
    assert template.skip_rules[0].action == "end_block"


def test_protocol_session_starts_in_progress() -> None:
    session = ProtocolSession(
        patient_id=UUID("00000000-0000-0000-0000-000000000001"),
        template_id="phq9",
        template_version="1",
        current_question_id="q1",
    )

    assert session.status == ProtocolSessionStatus.IN_PROGRESS
    assert session.score is None
    assert session.ended_by_skip is None


def test_protocol_answer_records_timezone_aware_timestamp() -> None:
    answer = ProtocolAnswer(question_id="q1", value=2)

    assert answer.answered_at.tzinfo is not None
    assert answer.answered_at.utcoffset() is not None


def test_journey_and_task_start_in_progress() -> None:
    journey = Journey(
        patient_id=UUID("00000000-0000-0000-0000-000000000001"),
        objective="Acompanhamento de saúde",
        tasks=[Task(title="Realizar primeiro check-in")],
    )

    assert journey.status == JourneyStatus.IN_PROGRESS
    assert journey.tasks[0].status == TaskStatus.IN_PROGRESS


def test_event_uses_event_name_taxonomy() -> None:
    event = Event(
        event_name=EventName.PATIENT_CREATED,
        patient_id_hash="hash",
        properties={"source": "test"},
    )

    assert event.event_name is EventName.PATIENT_CREATED
    assert event.event_name.value == "patient_created"
    assert isinstance(event.event_id, UUID)
    assert event.occurred_at.tzinfo is not None
    assert event.occurred_at.utcoffset() is not None
    assert event.patient_id_hash == "hash"
    assert event.properties == {"source": "test"}
