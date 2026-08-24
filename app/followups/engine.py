from datetime import timedelta
from typing import Callable

from app.domain.enums import JourneyStatus, TaskStatus
from app.domain.errors import UnsupportedFollowupRule
from app.followups.models import FollowupContext, FollowupDecision, FollowupRules


class FollowupEngine:
    def evaluate(
        self,
        context: FollowupContext,
        rules: FollowupRules,
    ) -> FollowupDecision:
        evaluators: dict[str, Callable[[], bool]] = {
            "consent_required": lambda: context.terms_accepted,
            "protocol_completed": lambda: context.protocol_completed,
            "journey_active": lambda: context.journey_status == JourneyStatus.IN_PROGRESS,
            "active_task_required": lambda: any(
                task.status == TaskStatus.IN_PROGRESS for task in context.tasks
            ),
            "cooldown": lambda: self._cooldown_expired(context, rules.cooldown_hours),
        }

        for rule in rules.rules:
            evaluator = evaluators.get(rule.type)
            if evaluator is None:
                raise UnsupportedFollowupRule(f"unsupported follow-up rule: {rule.type}")
            if not evaluator():
                return FollowupDecision(
                    eligible=False,
                    template_key=None,
                    reason=rule.reason,
                )

        return FollowupDecision(
            eligible=True,
            template_key=rules.template_key,
            reason=None,
        )

    def _cooldown_expired(
        self,
        context: FollowupContext,
        cooldown_hours: int,
    ) -> bool:
        if context.last_followup_eligible_at is None:
            return True

        elapsed = context.evaluated_at - context.last_followup_eligible_at
        return elapsed >= timedelta(hours=cooldown_hours)
