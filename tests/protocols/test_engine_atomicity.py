from uuid import UUID

import pytest

from app.domain.errors import UnsupportedProtocolRule
from app.domain.models import (
    ProtocolAnswer,
    ProtocolSession,
    ProtocolTemplate,
    Question,
    QuestionOption,
    SkipRule,
    SkipRuleCondition,
    SkipRuleTrigger,
)
from app.protocols.engine import ProtocolEngine

PATIENT_ID = UUID("00000000-0000-0000-0000-000000000001")


def test_process_answer_is_atomic_when_rule_evaluation_fails() -> None:
    template = ProtocolTemplate(
        template_id="atomicity_test",
        version="1.0",
        name="Atomicity test",
        prompt="Test prompt",
        questions=[
            Question(
                id="A",
                text="A",
                type="likert",
                options=[
                    QuestionOption(value=0, label="zero"),
                    QuestionOption(value=1, label="one"),
                ],
            ),
            Question(
                id="B",
                text="B",
                type="likert",
                options=[
                    QuestionOption(value=0, label="zero"),
                    QuestionOption(value=1, label="one"),
                ],
            ),
        ],
        skip_rules=[
            SkipRule(
                trigger=SkipRuleTrigger(after_question="B"),
                condition=SkipRuleCondition(
                    operator="unsupported",
                    questions=["A", "B"],
                    comparison="lt",
                    value=3,
                ),
                action="end_block",
            )
        ],
    )
    original_answer = ProtocolAnswer(question_id="A", value=1)
    session = ProtocolSession(
        patient_id=PATIENT_ID,
        template_id=template.template_id,
        template_version=template.version,
        current_question_id="B",
        answers=[original_answer],
    )
    answers_before = list(session.answers)

    with pytest.raises(UnsupportedProtocolRule):
        ProtocolEngine().process_answer(
            session,
            ProtocolAnswer(question_id="B", value=1),
            template,
        )

    assert session.answers == answers_before
