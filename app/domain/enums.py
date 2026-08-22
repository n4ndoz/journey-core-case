from enum import StrEnum


class ProtocolSessionStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class JourneyStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class TaskStatus(StrEnum):
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


class EventName(StrEnum):
    PATIENT_CREATED = "patient_created"
    TERMS_ACCEPTED = "terms_accepted"
    PROTOCOL_STARTED = "protocol_started"
    PROTOCOL_COMPLETED = "protocol_completed"
    JOURNEY_CREATED = "journey_created"
    TASK_COMPLETED = "task_completed"
    FOLLOWUP_ELIGIBLE = "followup_eligible"
    FOLLOWUP_SKIPPED = "followup_skipped"


class FollowupSkipReason(StrEnum):
    MISSING_CONSENT = "missing_consent"
    PROTOCOL_NOT_COMPLETED = "protocol_not_completed"
    JOURNEY_NOT_ACTIVE = "journey_not_active"
    NO_ACTIVE_TASK = "no_active_task"
    COOLDOWN = "cooldown"
