from enum import StrEnum
from numbers import Real

from pydantic import BaseModel

from app.domain.enums import ProtocolSessionStatus
from app.domain.errors import (
    InvalidAnswer,
    ProtocolAlreadyCompleted,
    QuestionMismatch,
    UnsupportedProtocolRule,
)
from app.domain.models import ProtocolAnswer, ProtocolSession, ProtocolTemplate, SkipRule


class ProtocolDecisionAction(StrEnum):
    CONTINUE = "continue"
    END_BLOCK = "end_block"
    COMPLETE = "complete"


class ProtocolDecision(BaseModel):
    action: ProtocolDecisionAction
    next_question_id: str | None
    score: int | float
    ended_by_skip: bool


class ProtocolEngine:
    def process_answer(
        self,
        session: ProtocolSession,
        answer: ProtocolAnswer,
        template: ProtocolTemplate,
    ) -> ProtocolDecision:
        if session.status == ProtocolSessionStatus.COMPLETED:
            raise ProtocolAlreadyCompleted()

        if answer.question_id != session.current_question_id:
            raise QuestionMismatch()

        question = next(
            (item for item in template.questions if item.id == answer.question_id),
            None,
        )
        if question is None:
            raise QuestionMismatch()

        if isinstance(answer.value, bool):
            raise InvalidAnswer("boolean answers are not allowed")

        allowed_values = [option.value for option in question.options]
        if answer.value not in allowed_values:
            raise InvalidAnswer()

        candidate_answers = [*session.answers, answer]
        score = self._calculate_score(candidate_answers)

        for rule in template.skip_rules:
            if rule.trigger.after_question != answer.question_id:
                continue
            if self._evaluate_rule(rule, candidate_answers):
                if rule.action != "end_block":
                    raise UnsupportedProtocolRule(f"unsupported action: {rule.action}")
                decision = ProtocolDecision(
                    action=ProtocolDecisionAction.END_BLOCK,
                    next_question_id=None,
                    score=score,
                    ended_by_skip=True,
                )
                session.answers.append(answer)
                return decision

        next_question_id = self._find_next_question(answer.question_id, template)
        if next_question_id is None:
            decision = ProtocolDecision(
                action=ProtocolDecisionAction.COMPLETE,
                next_question_id=None,
                score=score,
                ended_by_skip=False,
            )
            session.answers.append(answer)
            return decision

        decision = ProtocolDecision(
            action=ProtocolDecisionAction.CONTINUE,
            next_question_id=next_question_id,
            score=score,
            ended_by_skip=False,
        )
        session.answers.append(answer)
        return decision

    def _evaluate_rule(self, rule: SkipRule, answers: list[ProtocolAnswer]) -> bool:
        if rule.condition.operator != "sum":
            raise UnsupportedProtocolRule(
                f"unsupported operator: {rule.condition.operator}"
            )

        values_by_question = {answer.question_id: answer.value for answer in answers}
        try:
            values = [values_by_question[question_id] for question_id in rule.condition.questions]
        except KeyError as exc:
            raise InvalidAnswer("rule requires an unanswered question") from exc

        aggregate = self._sum_numeric(values)
        return self._compare(aggregate, rule.condition.comparison, rule.condition.value)

    def _compare(self, left: int | float, comparison: str, right: object) -> bool:
        if not self._is_numeric(right):
            raise InvalidAnswer("comparison value must be numeric")

        operations = {
            "lt": lambda: left < right,
            "lte": lambda: left <= right,
            "gt": lambda: left > right,
            "gte": lambda: left >= right,
            "equals": lambda: left == right,
            "not_equals": lambda: left != right,
        }
        operation = operations.get(comparison)
        if operation is None:
            raise UnsupportedProtocolRule(f"unsupported comparison: {comparison}")
        return operation()

    def _find_next_question(
        self,
        question_id: str,
        template: ProtocolTemplate,
    ) -> str | None:
        question_ids = [question.id for question in template.questions]
        try:
            current_index = question_ids.index(question_id)
        except ValueError as exc:
            raise QuestionMismatch() from exc

        next_index = current_index + 1
        return question_ids[next_index] if next_index < len(question_ids) else None

    def _calculate_score(self, answers: list[ProtocolAnswer]) -> int | float:
        return self._sum_numeric([answer.value for answer in answers])

    def _sum_numeric(self, values: list[object]) -> int | float:
        if any(not self._is_numeric(value) for value in values):
            raise InvalidAnswer("score values must be numeric")
        return sum(values)

    @staticmethod
    def _is_numeric(value: object) -> bool:
        return isinstance(value, Real) and not isinstance(value, bool)
