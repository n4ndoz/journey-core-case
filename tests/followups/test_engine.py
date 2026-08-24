from datetime import datetime, timedelta, timezone
import inspect

import pytest

import app.followups.engine as engine_module
from app.domain.enums import FollowupSkipReason, JourneyStatus, TaskStatus
from app.domain.errors import UnsupportedFollowupRule
from app.domain.models import Task
from app.followups.engine import FollowupEngine
from app.followups.loader import FollowupRulesLoader
from app.followups.models import FollowupContext, FollowupRule

EVALUATED_AT = datetime(2026, 8, 24, 12, 0, tzinfo=timezone.utc)


def make_context(**overrides: object) -> FollowupContext:
    data: dict[str, object] = {
        "terms_accepted": True,
        "protocol_completed": True,
        "journey_status": JourneyStatus.IN_PROGRESS,
        "tasks": [Task(title="Realizar acompanhamento")],
        "last_followup_eligible_at": None,
        "evaluated_at": EVALUATED_AT,
    }
    data.update(overrides)
    return FollowupContext.model_validate(data)


def evaluate(context: FollowupContext):
    return FollowupEngine().evaluate(context, FollowupRulesLoader().load())


def test_valid_context_is_eligible_with_configured_template_key() -> None:
    decision = evaluate(make_context())

    assert decision.eligible is True
    assert decision.template_key == "checkin_adesao"
    assert decision.reason is None


def test_missing_consent_returns_typed_reason() -> None:
    decision = evaluate(make_context(terms_accepted=False))

    assert decision.eligible is False
    assert decision.template_key is None
    assert decision.reason == FollowupSkipReason.MISSING_CONSENT


def test_incomplete_protocol_returns_typed_reason() -> None:
    decision = evaluate(make_context(protocol_completed=False))

    assert decision.reason == FollowupSkipReason.PROTOCOL_NOT_COMPLETED


def test_inactive_journey_returns_typed_reason() -> None:
    decision = evaluate(make_context(journey_status=JourneyStatus.COMPLETED))

    assert decision.reason == FollowupSkipReason.JOURNEY_NOT_ACTIVE


def test_no_active_task_returns_typed_reason() -> None:
    decision = evaluate(make_context(tasks=[]))

    assert decision.reason == FollowupSkipReason.NO_ACTIVE_TASK


def test_active_journey_with_only_completed_task_returns_no_active_task() -> None:
    decision = evaluate(
        make_context(
            tasks=[Task(title="Realizar acompanhamento", status=TaskStatus.COMPLETED)]
        )
    )

    assert decision.reason == FollowupSkipReason.NO_ACTIVE_TASK


def test_recent_followup_returns_cooldown() -> None:
    decision = evaluate(
        make_context(last_followup_eligible_at=EVALUATED_AT - timedelta(hours=1))
    )

    assert decision.reason == FollowupSkipReason.COOLDOWN


def test_followup_at_71h_59m_59s_is_still_in_cooldown() -> None:
    decision = evaluate(
        make_context(
            last_followup_eligible_at=EVALUATED_AT
            - timedelta(hours=71, minutes=59, seconds=59)
        )
    )

    assert decision.reason == FollowupSkipReason.COOLDOWN


def test_followup_exactly_72_hours_ago_is_eligible() -> None:
    decision = evaluate(
        make_context(last_followup_eligible_at=EVALUATED_AT - timedelta(hours=72))
    )

    assert decision.eligible is True


def test_followup_more_than_72_hours_ago_is_eligible() -> None:
    decision = evaluate(
        make_context(last_followup_eligible_at=EVALUATED_AT - timedelta(hours=73))
    )

    assert decision.eligible is True


def test_no_previous_followup_is_eligible() -> None:
    assert evaluate(make_context(last_followup_eligible_at=None)).eligible is True


def test_precedence_missing_consent_wins_all_other_failures() -> None:
    decision = evaluate(
        make_context(
            terms_accepted=False,
            protocol_completed=False,
            journey_status=JourneyStatus.COMPLETED,
            tasks=[],
            last_followup_eligible_at=EVALUATED_AT - timedelta(hours=1),
        )
    )

    assert decision.reason == FollowupSkipReason.MISSING_CONSENT


def test_precedence_protocol_wins_journey_task_and_cooldown() -> None:
    decision = evaluate(
        make_context(
            protocol_completed=False,
            journey_status=JourneyStatus.COMPLETED,
            tasks=[],
            last_followup_eligible_at=EVALUATED_AT - timedelta(hours=1),
        )
    )

    assert decision.reason == FollowupSkipReason.PROTOCOL_NOT_COMPLETED


def test_precedence_journey_wins_task_and_cooldown() -> None:
    decision = evaluate(
        make_context(
            journey_status=JourneyStatus.COMPLETED,
            tasks=[],
            last_followup_eligible_at=EVALUATED_AT - timedelta(hours=1),
        )
    )

    assert decision.reason == FollowupSkipReason.JOURNEY_NOT_ACTIVE


def test_precedence_task_wins_cooldown() -> None:
    decision = evaluate(
        make_context(
            tasks=[],
            last_followup_eligible_at=EVALUATED_AT - timedelta(hours=1),
        )
    )

    assert decision.reason == FollowupSkipReason.NO_ACTIVE_TASK


def test_template_key_comes_from_rules_configuration() -> None:
    rules = FollowupRulesLoader().load().model_copy(update={"template_key": "custom_checkin"})

    decision = FollowupEngine().evaluate(make_context(), rules)

    assert decision.template_key == "custom_checkin"


def test_cooldown_hours_comes_from_rules_configuration() -> None:
    rules = FollowupRulesLoader().load().model_copy(update={"cooldown_hours": 1})
    context = make_context(last_followup_eligible_at=EVALUATED_AT - timedelta(hours=2))

    decision = FollowupEngine().evaluate(context, rules)

    assert decision.eligible is True


def test_unknown_rule_fails_explicitly() -> None:
    rules = FollowupRulesLoader().load().model_copy(deep=True)
    rules.rules.insert(
        0,
        FollowupRule(type="unknown_rule", reason=FollowupSkipReason.COOLDOWN),
    )

    with pytest.raises(UnsupportedFollowupRule):
        FollowupEngine().evaluate(make_context(), rules)


def test_engine_has_no_repository_or_event_service_dependency() -> None:
    source = inspect.getsource(engine_module)

    assert "app.repositories" not in source
    assert "EventService" not in source
