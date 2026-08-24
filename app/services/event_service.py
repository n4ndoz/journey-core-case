from datetime import datetime, timezone
from typing import TypeAlias

from app.domain.event_properties import (
    EventProperties,
    FollowupEligibleProperties,
    FollowupSkippedProperties,
    JourneyCreatedProperties,
    PatientCreatedProperties,
    ProtocolCompletedProperties,
    ProtocolStartedProperties,
    TaskCompletedProperties,
    TermsAcceptedProperties,
)
from app.domain.enums import EventName
from app.domain.models import Event
from app.repositories.in_memory import EventRepository

TypedEventProperties: TypeAlias = (
    PatientCreatedProperties
    | TermsAcceptedProperties
    | ProtocolStartedProperties
    | ProtocolCompletedProperties
    | JourneyCreatedProperties
    | TaskCompletedProperties
    | FollowupEligibleProperties
    | FollowupSkippedProperties
)

_EVENT_PROPERTY_TYPES: dict[EventName, type[EventProperties]] = {
    EventName.PATIENT_CREATED: PatientCreatedProperties,
    EventName.TERMS_ACCEPTED: TermsAcceptedProperties,
    EventName.PROTOCOL_STARTED: ProtocolStartedProperties,
    EventName.PROTOCOL_COMPLETED: ProtocolCompletedProperties,
    EventName.JOURNEY_CREATED: JourneyCreatedProperties,
    EventName.TASK_COMPLETED: TaskCompletedProperties,
    EventName.FOLLOWUP_ELIGIBLE: FollowupEligibleProperties,
    EventName.FOLLOWUP_SKIPPED: FollowupSkippedProperties,
}


class EventService:
    def __init__(self, repository: EventRepository) -> None:
        self._repository = repository

    def emit(
        self,
        event_name: EventName,
        patient_id_hash: str,
        properties: TypedEventProperties,
        occurred_at: datetime | None = None,
    ) -> Event:
        expected_type = _EVENT_PROPERTY_TYPES[event_name]
        if not isinstance(properties, expected_type):
            raise TypeError(
                f"properties for {event_name.value} must be {expected_type.__name__}"
            )

        event = Event(
            occurred_at=occurred_at or datetime.now(timezone.utc),
            event_name=event_name,
            patient_id_hash=patient_id_hash,
            properties=properties.model_dump(mode="json"),
        )
        self._repository.append(event)
        return event
