from app.followups.engine import FollowupEngine
from app.followups.loader import FollowupRulesLoader
from app.protocols.engine import ProtocolEngine
from app.protocols.loader import TemplateLoader
from app.repositories.in_memory import (
    EventRepository,
    JourneyRepository,
    PatientRepository,
    ProtocolRepository,
)
from app.security.hashing import PhoneHasher
from app.services.event_service import EventService
from app.services.followup_service import FollowupService
from app.services.journey_service import JourneyService
from app.services.patient_service import PatientService
from app.services.protocol_service import ProtocolService

patient_repository = PatientRepository()
protocol_repository = ProtocolRepository()
journey_repository = JourneyRepository()
event_repository = EventRepository()

template_loader = TemplateLoader()
followup_rules_loader = FollowupRulesLoader()
event_service = EventService(event_repository)
journey_service = JourneyService(journey_repository, event_service)
patient_service = PatientService(patient_repository, PhoneHasher(), event_service)
protocol_service = ProtocolService(
    patient_repository,
    protocol_repository,
    template_loader,
    ProtocolEngine(),
    event_service,
    journey_service,
)
followup_service = FollowupService(
    patient_repository,
    protocol_repository,
    journey_repository,
    event_repository,
    followup_rules_loader,
    FollowupEngine(),
    event_service,
)
