from datetime import date, datetime, timezone
from typing import Self
from uuid import UUID, uuid4

from pydantic import BaseModel, Field, model_validator

from app.domain.enums import EventName, JourneyStatus, ProtocolSessionStatus, TaskStatus


class Patient(BaseModel):
    patient_id: UUID = Field(default_factory=uuid4)
    phone: str
    phone_hash: str
    name: str
    birth_date: date
    sex: str
    terms_accepted: bool = False


class QuestionOption(BaseModel):
    value: int | str
    label: str = Field(min_length=1)


class Question(BaseModel):
    id: str = Field(min_length=1)
    text: str = Field(min_length=1)
    type: str = Field(min_length=1)
    options: list[QuestionOption]


class SkipRuleTrigger(BaseModel):
    after_question: str = Field(min_length=1)


class SkipRuleCondition(BaseModel):
    operator: str = Field(min_length=1)
    questions: list[str] = Field(min_length=1)
    comparison: str = Field(min_length=1)
    value: int | float | str


class SkipRule(BaseModel):
    trigger: SkipRuleTrigger
    condition: SkipRuleCondition
    action: str = Field(min_length=1)


class ProtocolTemplate(BaseModel):
    template_id: str = Field(min_length=1)
    version: str = Field(min_length=1)
    name: str = Field(min_length=1)
    prompt: str = ""
    questions: list[Question] = Field(min_length=1)
    skip_rules: list[SkipRule] = Field(default_factory=list)

    @model_validator(mode="after")
    def validate_internal_references(self) -> Self:
        question_ids = [question.id for question in self.questions]
        if len(question_ids) != len(set(question_ids)):
            raise ValueError("question ids must be unique")

        known_ids = set(question_ids)
        for rule in self.skip_rules:
            if rule.trigger.after_question not in known_ids:
                raise ValueError("skip rule trigger references an unknown question")
            if any(question_id not in known_ids for question_id in rule.condition.questions):
                raise ValueError("skip rule condition references an unknown question")

        return self


class ProtocolAnswer(BaseModel):
    question_id: str
    value: int | float | str
    answered_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


class ProtocolSession(BaseModel):
    session_id: UUID = Field(default_factory=uuid4)
    patient_id: UUID
    template_id: str
    template_version: str
    status: ProtocolSessionStatus = ProtocolSessionStatus.IN_PROGRESS
    current_question_id: str | None = None
    answers: list[ProtocolAnswer] = Field(default_factory=list)
    score: int | float | None = None
    ended_by_skip: bool | None = None


class Task(BaseModel):
    task_id: UUID = Field(default_factory=uuid4)
    title: str
    status: TaskStatus = TaskStatus.IN_PROGRESS


class Journey(BaseModel):
    journey_id: UUID = Field(default_factory=uuid4)
    patient_id: UUID
    status: JourneyStatus = JourneyStatus.IN_PROGRESS
    objective: str
    tasks: list[Task] = Field(default_factory=list)


class Event(BaseModel):
    event_id: UUID = Field(default_factory=uuid4)
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    event_name: EventName
    patient_id_hash: str
    properties: dict[str, object] = Field(default_factory=dict)
