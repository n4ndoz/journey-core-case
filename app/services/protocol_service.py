from uuid import UUID

from app.domain.enums import EventName, ProtocolSessionStatus
from app.domain.errors import (
    ConsentRequired,
    PatientNotFound,
    ProtocolSessionNotFound,
)
from app.domain.event_properties import ProtocolCompletedProperties, ProtocolStartedProperties
from app.domain.models import ProtocolAnswer, ProtocolSession
from app.protocols.engine import ProtocolDecisionAction, ProtocolEngine
from app.protocols.loader import TemplateLoader
from app.repositories.in_memory import PatientRepository, ProtocolRepository
from app.services.event_service import EventService
from app.services.journey_service import JourneyService


class ProtocolService:
    def __init__(
        self,
        patient_repository: PatientRepository,
        protocol_repository: ProtocolRepository,
        template_loader: TemplateLoader,
        protocol_engine: ProtocolEngine,
        event_service: EventService,
        journey_service: JourneyService,
    ) -> None:
        self._patient_repository = patient_repository
        self._protocol_repository = protocol_repository
        self._template_loader = template_loader
        self._protocol_engine = protocol_engine
        self._event_service = event_service
        self._journey_service = journey_service

    def start_protocol(self, patient_id: UUID, template_id: str) -> ProtocolSession:
        patient = self._patient_repository.get(patient_id)
        if patient is None:
            raise PatientNotFound()
        if not patient.terms_accepted:
            raise ConsentRequired()

        template = self._template_loader.load(template_id)
        session = ProtocolSession(
            patient_id=patient.patient_id,
            template_id=template.template_id,
            template_version=template.version,
            current_question_id=template.questions[0].id,
        )
        self._protocol_repository.save(session)
        self._event_service.emit(
            EventName.PROTOCOL_STARTED,
            patient.patient_id_hash,
            ProtocolStartedProperties(
                template_id=template.template_id,
                template_version=template.version,
            ),
        )
        return session

    def submit_answer(self, session_id: UUID, answer: ProtocolAnswer) -> ProtocolSession:
        session = self._protocol_repository.get(session_id)
        if session is None:
            raise ProtocolSessionNotFound()

        patient = self._patient_repository.get(session.patient_id)
        if patient is None:
            raise PatientNotFound()

        template = self._template_loader.load(
            session.template_id,
            version=session.template_version,
        )
        decision = self._protocol_engine.process_answer(session, answer, template)

        if decision.action == ProtocolDecisionAction.CONTINUE:
            session.current_question_id = decision.next_question_id
            self._protocol_repository.save(session)
            return session

        session.status = ProtocolSessionStatus.COMPLETED
        session.current_question_id = None
        session.score = decision.score
        session.ended_by_skip = decision.ended_by_skip
        self._protocol_repository.save(session)
        self._event_service.emit(
            EventName.PROTOCOL_COMPLETED,
            patient.patient_id_hash,
            ProtocolCompletedProperties(
                template_id=session.template_id,
                template_version=session.template_version,
                score=decision.score,
                ended_by_skip=decision.ended_by_skip,
            ),
        )
        self._journey_service.create_journey(
            patient_id=patient.patient_id,
            patient_id_hash=patient.patient_id_hash,
            protocol_session=session,
        )
        return session
