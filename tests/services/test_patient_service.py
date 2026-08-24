from datetime import date

from app.domain.enums import EventName
from app.repositories.in_memory import EventRepository, PatientRepository
from app.security.hashing import PhoneHasher
from app.services.event_service import EventService
from app.services.patient_service import PatientService


def make_service() -> tuple[PatientService, PatientRepository, EventRepository]:
    patient_repository = PatientRepository()
    event_repository = EventRepository()
    return (
        PatientService(
            patient_repository,
            PhoneHasher(salt="test-salt"),
            EventService(event_repository),
        ),
        patient_repository,
        event_repository,
    )


def test_create_patient_hashes_persists_and_emits_events_in_order() -> None:
    service, patient_repository, event_repository = make_service()

    patient = service.create_patient(
        phone="+55 (11) 99999-0000",
        name="Paciente Teste",
        birth_date=date(1990, 1, 1),
        sex="F",
        terms_accepted=True,
    )

    assert patient.phone_hash == PhoneHasher(salt="test-salt").hash(patient.phone)
    assert patient_repository.get(patient.patient_id) == patient
    assert [event.event_name for event in event_repository.list_all()] == [
        EventName.PATIENT_CREATED,
        EventName.TERMS_ACCEPTED,
    ]


def test_patient_without_consent_is_allowed_and_emits_only_patient_created() -> None:
    service, _, event_repository = make_service()

    patient = service.create_patient(
        phone="5511999990000",
        name="Paciente Teste",
        birth_date=date(1990, 1, 1),
        sex="F",
        terms_accepted=False,
    )

    assert patient.terms_accepted is False
    assert [event.event_name for event in event_repository.list_all()] == [
        EventName.PATIENT_CREATED
    ]


def test_patient_events_do_not_contain_pii() -> None:
    service, _, event_repository = make_service()
    phone = "+55 (11) 98888-7777"
    name = "Nome Sensível"

    service.create_patient(
        phone=phone,
        name=name,
        birth_date=date(1985, 5, 20),
        sex="M",
        terms_accepted=True,
    )

    for event in event_repository.list_all():
        serialized = event.model_dump_json()
        assert phone not in serialized
        assert name not in serialized
        assert "birth_date" not in serialized
        assert event.properties == {}
