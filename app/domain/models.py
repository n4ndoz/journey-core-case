from datetime import date, datetime, timezone
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

from app.domain.enums import EventName, JourneyStatus, ProtocolSessionStatus, TaskStatus


class Patient(BaseModel):
    patient_id: UUID = Field(default_factory=uuid4)
    phone: str
    phone_hash: str
    name: str
    birth_date: date
    sex: str
    terms_accepted: bool = False


class Question(BaseModel):
    id: str
    text: str
    type: str
    options: list[int | str] = Field(default_factory=list)


class SkipRuleTrigger(BaseModel):
    after_question: str


class SkipRuleCondition(BaseModel):
    operator: str
    questions: list[str]
    comparison: str
    value: int | float | str


class SkipRule(BaseModel):
    trigger: SkipRuleTrigger
    condition: SkipRuleCondition
    action: str


class ProtocolTemplate(BaseModel):
    template_id: str
    version: str
    name: str
    questions: list[Question]
    skip_rules: list[SkipRule] = Field(default_factory=list)


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
