from datetime import date, datetime
from uuid import UUID

from pydantic import BaseModel, field_validator

from app.domain.enums import (
    EventName,
    FollowupSkipReason,
    JourneyStatus,
    ProtocolSessionStatus,
    TaskStatus,
)


class PatientCreateRequest(BaseModel):
    phone: str
    name: str
    birth_date: date
    sex: str
    terms_accepted: bool


class PatientResponse(BaseModel):
    patient_id: UUID
    phone: str
    name: str
    birth_date: date
    sex: str
    terms_accepted: bool


class ProtocolStartRequest(BaseModel):
    template_id: str


class QuestionOptionResponse(BaseModel):
    value: int | str
    label: str


class QuestionResponse(BaseModel):
    id: str
    text: str
    type: str
    options: list[QuestionOptionResponse]


class ProtocolStartResponse(BaseModel):
    session_id: UUID
    status: ProtocolSessionStatus
    prompt: str | None
    current_question: QuestionResponse


class ProtocolAnswerRequest(BaseModel):
    question_id: str
    value: int | float | str

    @field_validator("value", mode="before")
    @classmethod
    def reject_boolean_value(cls, value: object) -> object:
        if isinstance(value, bool):
            raise ValueError("boolean answers are not allowed")
        return value


class ProtocolAnswerResponse(BaseModel):
    session_id: UUID
    status: ProtocolSessionStatus
    next_question: QuestionResponse | None = None
    score: int | float | None = None
    ended_by_skip: bool | None = None


class TaskResponse(BaseModel):
    task_id: UUID
    title: str
    status: TaskStatus


class TaskCompletionResponse(BaseModel):
    journey_id: UUID
    task_id: UUID
    status: TaskStatus


class JourneyResponse(BaseModel):
    journey_id: UUID
    status: JourneyStatus
    objective: str
    tasks: list[TaskResponse]


class FollowupEvaluateRequest(BaseModel):
    patient_id: UUID


class FollowupDecisionResponse(BaseModel):
    eligible: bool
    template_key: str | None
    reason: FollowupSkipReason | None


class EventResponse(BaseModel):
    event_id: UUID
    occurred_at: datetime
    event_name: EventName
    patient_id_hash: str
    properties: dict[str, object]
