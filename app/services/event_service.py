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


class EventService:
    def __init__(self, repository: EventRepository) -> None:
        self._repository = repository

    def emit(
        self,
        event_name: EventName,
        patient_id_hash: str,
        properties: TypedEventProperties,
    ) -> Event:
        if not isinstance(properties, EventProperties):
            raise TypeError("properties must be a typed EventProperties model")

        event = Event(
            occurred_at=datetime.now(timezone.utc),
            event_name=event_name,
            patient_id_hash=patient_id_hash,
            properties=properties.model_dump(mode="json"),
        )
        self._repository.append(event)
        return event
