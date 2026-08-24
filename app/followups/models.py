from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.domain.enums import FollowupSkipReason, JourneyStatus
from app.domain.models import Task


class FollowupRule(BaseModel):
    type: str = Field(min_length=1)
    reason: FollowupSkipReason


class FollowupRules(BaseModel):
    template_key: str = Field(min_length=1)
    cooldown_hours: int = Field(gt=0)
    rules: list[FollowupRule] = Field(min_length=1)


class FollowupContext(BaseModel):
    terms_accepted: bool
    protocol_completed: bool
    journey_status: JourneyStatus
    tasks: list[Task]
    last_followup_eligible_at: datetime | None = None
    evaluated_at: datetime

    @field_validator("last_followup_eligible_at", "evaluated_at")
    @classmethod
    def validate_timezone_aware(cls, value: datetime | None) -> datetime | None:
        if value is not None and (value.tzinfo is None or value.utcoffset() is None):
            raise ValueError("follow-up timestamps must be timezone-aware")
        return value


class FollowupDecision(BaseModel):
    eligible: bool
    template_key: str | None
    reason: FollowupSkipReason | None
