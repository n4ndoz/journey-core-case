from datetime import datetime, timezone
from uuid import UUID

from app.domain.enums import EventName, JourneyStatus, ProtocolSessionStatus
from app.domain.errors import PatientNotFound
from app.domain.event_properties import FollowupEligibleProperties, FollowupSkippedProperties
from app.followups.engine import FollowupEngine
from app.followups.loader import FollowupRulesLoader
from app.followups.models import FollowupContext, FollowupDecision
from app.repositories.in_memory import (
    EventRepository,
    JourneyRepository,
    PatientRepository,
    ProtocolRepository,
)
from app.services.event_service import EventService


class FollowupService:
    def __init__(
        self,
        patient_repository: PatientRepository,
        protocol_repository: ProtocolRepository,
        journey_repository: JourneyRepository,
        event_repository: EventRepository,
        rules_loader: FollowupRulesLoader,
        followup_engine: FollowupEngine,
        event_service: EventService,
    ) -> None:
        self._patient_repository = patient_repository
        self._protocol_repository = protocol_repository
        self._journey_repository = journey_repository
        self._event_repository = event_repository
        self._rules_loader = rules_loader
        self._followup_engine = followup_engine
        self._event_service = event_service

    def evaluate(
        self,
        patient_id: UUID,
        evaluated_at: datetime | None = None,
    ) -> FollowupDecision:
        patient = self._patient_repository.get(patient_id)
        if patient is None:
            raise PatientNotFound()

        sessions = self._protocol_repository.list_by_patient(patient.patient_id)
        protocol_completed = any(
            session.status == ProtocolSessionStatus.COMPLETED for session in sessions
        )

        journey = self._journey_repository.get_by_patient(patient.patient_id)
        journey_status = journey.status if journey is not None else JourneyStatus.COMPLETED
        tasks = journey.tasks if journey is not None else []

        history = self._event_repository.list_by_patient(patient.phone_hash)
        eligible_events = [
            event for event in history if event.event_name == EventName.FOLLOWUP_ELIGIBLE
        ]
        last_followup_eligible_at = (
            max(event.occurred_at for event in eligible_events) if eligible_events else None
        )

        rules = self._rules_loader.load()
        context = FollowupContext(
            terms_accepted=patient.terms_accepted,
            protocol_completed=protocol_completed,
            journey_status=journey_status,
            tasks=tasks,
            last_followup_eligible_at=last_followup_eligible_at,
            evaluated_at=evaluated_at or datetime.now(timezone.utc),
        )
        decision = self._followup_engine.evaluate(context, rules)

        if decision.eligible:
            if decision.template_key is None:
                raise ValueError("eligible follow-up decision requires template_key")
            self._event_service.emit(
                EventName.FOLLOWUP_ELIGIBLE,
                patient.phone_hash,
                FollowupEligibleProperties(template_key=decision.template_key),
            )
        else:
            if decision.reason is None:
                raise ValueError("skipped follow-up decision requires reason")
            self._event_service.emit(
                EventName.FOLLOWUP_SKIPPED,
                patient.phone_hash,
                FollowupSkippedProperties(reason=decision.reason),
            )

        return decision
