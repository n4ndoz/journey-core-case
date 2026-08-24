from uuid import UUID

from pydantic import BaseModel, ConfigDict

from app.domain.enums import FollowupSkipReason


class EventProperties(BaseModel):
    model_config = ConfigDict(extra="forbid")


class PatientCreatedProperties(EventProperties):
    pass


class TermsAcceptedProperties(EventProperties):
    pass


class ProtocolStartedProperties(EventProperties):
    template_id: str
    template_version: str


class ProtocolCompletedProperties(EventProperties):
    template_id: str
    template_version: str
    score: int | float
    ended_by_skip: bool


class JourneyCreatedProperties(EventProperties):
    journey_id: UUID
    objective: str


class TaskCompletedProperties(EventProperties):
    journey_id: UUID
    task_id: UUID


class FollowupEligibleProperties(EventProperties):
    template_key: str


class FollowupSkippedProperties(EventProperties):
    reason: FollowupSkipReason
