from app.domain.enums import FollowupSkipReason
from app.followups.loader import FollowupRulesLoader
from app.followups.models import FollowupRules


def test_loader_returns_typed_default_rules_in_expected_order() -> None:
    rules = FollowupRulesLoader().load()

    assert isinstance(rules, FollowupRules)
    assert rules.template_key == "checkin_adesao"
    assert rules.cooldown_hours == 72
    assert [rule.type for rule in rules.rules] == [
        "consent_required",
        "protocol_completed",
        "journey_active",
        "active_task_required",
        "cooldown",
    ]
    assert [rule.reason for rule in rules.rules] == [
        FollowupSkipReason.MISSING_CONSENT,
        FollowupSkipReason.PROTOCOL_NOT_COMPLETED,
        FollowupSkipReason.JOURNEY_NOT_ACTIVE,
        FollowupSkipReason.NO_ACTIVE_TASK,
        FollowupSkipReason.COOLDOWN,
    ]
