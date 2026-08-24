from uuid import UUID

import pytest

from app.domain.enums import ProtocolSessionStatus
from app.domain.errors import (
    InvalidAnswer,
    ProtocolAlreadyCompleted,
    QuestionMismatch,
    UnsupportedProtocolRule,
)
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
from app.protocols.engine import ProtocolDecisionAction, ProtocolEngine
from app.protocols.loader import TemplateLoader

PATIENT_ID = UUID("00000000-0000-0000-0000-000000000001")


def make_session(current_question_id: str = "1") -> ProtocolSession:
    return ProtocolSession(
        patient_id=PATIENT_ID,
        template_id="phq9",
        template_version="1.0",
        current_question_id=current_question_id,
    )


def make_generic_template(
    *,
    comparison: str = "lt",
    threshold: int = 3,
    operator: str = "sum",
    action: str = "end_block",
) -> ProtocolTemplate:
    options = [
        QuestionOption(value=0, label="zero"),
        QuestionOption(value=1, label="one"),
        QuestionOption(value=2, label="two"),
        QuestionOption(value=3, label="three"),
    ]
    return ProtocolTemplate(
        template_id="test_protocol",
        version="1.0",
        name="Test protocol",
        prompt="Test prompt",
        questions=[
            Question(id="A", text="A", type="likert", options=options),
            Question(id="B", text="B", type="likert", options=options),
            Question(id="C", text="C", type="likert", options=options),
        ],
        skip_rules=[
            SkipRule(
                trigger=SkipRuleTrigger(after_question="B"),
                condition=SkipRuleCondition(
                    operator=operator,
                    questions=["A", "B"],
                    comparison=comparison,
                    value=threshold,
                ),
                action=action,
            )
        ],
    )


def test_first_valid_answer_continues_to_next_question() -> None:
    engine = ProtocolEngine()
    template = TemplateLoader().load("phq9")
    session = make_session()

    decision = engine.process_answer(session, ProtocolAnswer(question_id="1", value=2), template)

    assert decision.action == ProtocolDecisionAction.CONTINUE
    assert decision.next_question_id == "2"
    assert session.answers[-1].value == 2


def test_question_out_of_order_raises_question_mismatch_without_recording() -> None:
    engine = ProtocolEngine()
    template = TemplateLoader().load("phq9")
    session = make_session()

    with pytest.raises(QuestionMismatch):
        engine.process_answer(session, ProtocolAnswer(question_id="2", value=1), template)

    assert session.answers == []


def test_answer_outside_options_raises_invalid_answer_without_recording() -> None:
    engine = ProtocolEngine()
    template = TemplateLoader().load("phq9")
    session = make_session()

    with pytest.raises(InvalidAnswer):
        engine.process_answer(session, ProtocolAnswer(question_id="1", value=4), template)

    assert session.answers == []


def test_completed_session_rejects_new_answer() -> None:
    engine = ProtocolEngine()
    template = TemplateLoader().load("phq9")
    session = make_session()
    session.status = ProtocolSessionStatus.COMPLETED

    with pytest.raises(ProtocolAlreadyCompleted):
        engine.process_answer(session, ProtocolAnswer(question_id="1", value=1), template)

    assert session.answers == []


def test_phq2_skip_returns_partial_score_and_ended_by_skip() -> None:
    engine = ProtocolEngine()
    template = TemplateLoader().load("phq9")
    session = make_session()

    first = engine.process_answer(session, ProtocolAnswer(question_id="1", value=1), template)
    session.current_question_id = first.next_question_id
    decision = engine.process_answer(session, ProtocolAnswer(question_id="2", value=1), template)

    assert decision.action == ProtocolDecisionAction.END_BLOCK
    assert decision.next_question_id is None
    assert decision.score == 2
    assert decision.ended_by_skip is True


def test_phq2_boundary_continues_to_question_three() -> None:
    engine = ProtocolEngine()
    template = TemplateLoader().load("phq9")
    session = make_session()

    first = engine.process_answer(session, ProtocolAnswer(question_id="1", value=2), template)
    session.current_question_id = first.next_question_id
    decision = engine.process_answer(session, ProtocolAnswer(question_id="2", value=1), template)

    assert decision.action == ProtocolDecisionAction.CONTINUE
    assert decision.next_question_id == "3"
    assert decision.score == 3


def test_rule_is_only_evaluated_after_configured_question() -> None:
    engine = ProtocolEngine()
    template = make_generic_template(operator="unsupported")
    session = ProtocolSession(
        patient_id=PATIENT_ID,
        template_id=template.template_id,
        template_version=template.version,
        current_question_id="A",
    )

    decision = engine.process_answer(session, ProtocolAnswer(question_id="A", value=1), template)

    assert decision.action == ProtocolDecisionAction.CONTINUE
    assert decision.next_question_id == "B"


def test_full_protocol_completes_with_total_score() -> None:
    engine = ProtocolEngine()
    template = TemplateLoader().load("phq9")
    session = make_session()
    values = [2, 1, 1, 2, 0, 3, 1, 2, 1]

    decision = None
    for question, value in zip(template.questions, values, strict=True):
        decision = engine.process_answer(
            session,
            ProtocolAnswer(question_id=question.id, value=value),
            template,
        )
        session.current_question_id = decision.next_question_id

    assert decision is not None
    assert decision.action == ProtocolDecisionAction.COMPLETE
    assert decision.next_question_id is None
    assert decision.ended_by_skip is False
    assert decision.score == sum(values)


@pytest.mark.parametrize(
    ("comparison", "threshold", "expected_skip"),
    [
        ("lt", 3, True),
        ("lte", 2, True),
        ("gt", 1, True),
        ("gte", 2, True),
        ("equals", 2, True),
        ("not_equals", 3, True),
    ],
)
def test_supported_comparisons(
    comparison: str,
    threshold: int,
    expected_skip: bool,
) -> None:
    engine = ProtocolEngine()
    template = make_generic_template(comparison=comparison, threshold=threshold)
    session = ProtocolSession(
        patient_id=PATIENT_ID,
        template_id=template.template_id,
        template_version=template.version,
        current_question_id="A",
    )

    first = engine.process_answer(session, ProtocolAnswer(question_id="A", value=1), template)
    session.current_question_id = first.next_question_id
    decision = engine.process_answer(session, ProtocolAnswer(question_id="B", value=1), template)

    assert (decision.action == ProtocolDecisionAction.END_BLOCK) is expected_skip


def test_generic_template_proves_engine_does_not_depend_on_phq9() -> None:
    engine = ProtocolEngine()
    template = make_generic_template(threshold=5)
    session = ProtocolSession(
        patient_id=PATIENT_ID,
        template_id=template.template_id,
        template_version=template.version,
        current_question_id="A",
    )

    first = engine.process_answer(session, ProtocolAnswer(question_id="A", value=2), template)
    session.current_question_id = first.next_question_id
    decision = engine.process_answer(session, ProtocolAnswer(question_id="B", value=2), template)

    assert decision.action == ProtocolDecisionAction.END_BLOCK
    assert decision.score == 4


def test_unsupported_operator_fails_explicitly() -> None:
    engine = ProtocolEngine()
    template = make_generic_template(operator="average")
    session = ProtocolSession(
        patient_id=PATIENT_ID,
        template_id=template.template_id,
        template_version=template.version,
        current_question_id="B",
        answers=[ProtocolAnswer(question_id="A", value=1)],
    )

    with pytest.raises(UnsupportedProtocolRule):
        engine.process_answer(session, ProtocolAnswer(question_id="B", value=1), template)


def test_unsupported_comparison_fails_explicitly() -> None:
    engine = ProtocolEngine()
    template = make_generic_template(comparison="contains")
    session = ProtocolSession(
        patient_id=PATIENT_ID,
        template_id=template.template_id,
        template_version=template.version,
        current_question_id="B",
        answers=[ProtocolAnswer(question_id="A", value=1)],
    )

    with pytest.raises(UnsupportedProtocolRule):
        engine.process_answer(session, ProtocolAnswer(question_id="B", value=1), template)


def test_unsupported_action_fails_explicitly() -> None:
    engine = ProtocolEngine()
    template = make_generic_template(action="jump")
    session = ProtocolSession(
        patient_id=PATIENT_ID,
        template_id=template.template_id,
        template_version=template.version,
        current_question_id="B",
        answers=[ProtocolAnswer(question_id="A", value=1)],
    )

    with pytest.raises(UnsupportedProtocolRule):
        engine.process_answer(session, ProtocolAnswer(question_id="B", value=1), template)


def test_non_numeric_answer_is_rejected_when_scoring() -> None:
    engine = ProtocolEngine()
    template = ProtocolTemplate(
        template_id="text_protocol",
        version="1.0",
        name="Text",
        prompt="Text",
        questions=[
            Question(
                id="A",
                text="A",
                type="choice",
                options=[QuestionOption(value="yes", label="Yes")],
            )
        ],
    )
    session = ProtocolSession(
        patient_id=PATIENT_ID,
        template_id=template.template_id,
        template_version=template.version,
        current_question_id="A",
    )

    with pytest.raises(InvalidAnswer):
        engine.process_answer(session, ProtocolAnswer(question_id="A", value="yes"), template)
