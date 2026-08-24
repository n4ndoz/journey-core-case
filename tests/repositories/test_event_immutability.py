from app.domain.enums import EventName
from app.domain.event_properties import PatientCreatedProperties
from app.domain.models import Event
from app.repositories.in_memory import EventRepository
from app.services.event_service import EventService


PATIENT_HASH = "patient-hash"


def test_mutating_event_returned_by_emit_does_not_change_persisted_event() -> None:
    repository = EventRepository()
    service = EventService(repository)

    emitted = service.emit(
        EventName.PATIENT_CREATED,
        PATIENT_HASH,
        PatientCreatedProperties(),
    )
    emitted.properties["phone"] = "+5511999999999"

    persisted = repository.list_all()[0]
    assert persisted.properties == {}


def test_mutating_event_from_list_all_does_not_change_persisted_event() -> None:
    repository = EventRepository()
    repository.append(
        Event(
            event_name=EventName.PATIENT_CREATED,
            patient_id_hash=PATIENT_HASH,
        )
    )

    listed = repository.list_all()[0]
    listed.properties["name"] = "Injected Name"

    assert repository.list_all()[0].properties == {}


def test_mutating_event_from_list_by_patient_does_not_change_persisted_event() -> None:
    repository = EventRepository()
    repository.append(
        Event(
            event_name=EventName.PATIENT_CREATED,
            patient_id_hash=PATIENT_HASH,
        )
    )

    listed = repository.list_by_patient(PATIENT_HASH)[0]
    listed.properties["birth_date"] = "1990-01-01"

    assert repository.list_by_patient(PATIENT_HASH)[0].properties == {}


def test_mutating_original_event_after_append_does_not_contaminate_store_with_pii() -> None:
    repository = EventRepository()
    event = Event(
        event_name=EventName.PATIENT_CREATED,
        patient_id_hash=PATIENT_HASH,
    )

    repository.append(event)
    event.properties.update(
        {
            "phone": "+5511999999999",
            "name": "Injected Name",
            "birth_date": "1990-01-01",
        }
    )

    persisted = repository.list_all()[0]
    assert "phone" not in persisted.properties
    assert "name" not in persisted.properties
    assert "birth_date" not in persisted.properties
