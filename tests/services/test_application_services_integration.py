from datetime import date

from app.domain.enums import EventName, FollowupSkipReason
from app.domain.models import ProtocolAnswer
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


def test_application_services_end_to_end_without_http_and_without_pii_events() -> None:
    patient_repository = PatientRepository()
    protocol_repository = ProtocolRepository()
    journey_repository = JourneyRepository()
    event_repository = EventRepository()
    event_service = EventService(event_repository)

    patient_service = PatientService(
        patient_repository,
        PhoneHasher(salt="integration-salt"),
        event_service,
    )
    journey_service = JourneyService(journey_repository, event_service)
    protocol_service = ProtocolService(
        patient_repository,
        protocol_repository,
        TemplateLoader(),
        ProtocolEngine(),
        event_service,
        journey_service,
    )
    followup_service = FollowupService(
        patient_repository,
        protocol_repository,
        journey_repository,
        event_repository,
        FollowupRulesLoader(),
        FollowupEngine(),
        event_service,
    )

    phone = "+55 (11) 97777-6666"
    name = "Paciente Integração"
    patient = patient_service.create_patient(
        phone=phone,
        name=name,
        birth_date=date(1992, 4, 10),
        sex="F",
        terms_accepted=True,
    )
    session = protocol_service.start_protocol(patient.patient_id, "phq9")
    protocol_service.submit_answer(
        session.session_id,
        ProtocolAnswer(question_id="1", value=1),
    )
    completed = protocol_service.submit_answer(
        session.session_id,
        ProtocolAnswer(question_id="2", value=1),
    )

    journey = journey_repository.get_by_patient(patient.patient_id)
    assert completed.score == 2
    assert completed.ended_by_skip is True
    assert journey is not None
    assert len(journey.tasks) == 1

    first_followup = followup_service.evaluate(patient.patient_id)
    second_followup = followup_service.evaluate(patient.patient_id)

    assert first_followup.eligible is True
    assert first_followup.template_key == "checkin_adesao"
    assert second_followup.eligible is False
    assert second_followup.reason == FollowupSkipReason.COOLDOWN

    events = event_repository.list_all()
    assert [event.event_name for event in events] == [
        EventName.PATIENT_CREATED,
        EventName.TERMS_ACCEPTED,
        EventName.PROTOCOL_STARTED,
        EventName.PROTOCOL_COMPLETED,
        EventName.JOURNEY_CREATED,
        EventName.FOLLOWUP_ELIGIBLE,
        EventName.FOLLOWUP_SKIPPED,
    ]

    for event in events:
        serialized = event.model_dump_json()
        assert phone not in serialized
        assert name not in serialized
        assert "birth_date" not in serialized
        assert "phone" not in event.properties
        assert "name" not in event.properties
        assert "birth_date" not in event.properties
