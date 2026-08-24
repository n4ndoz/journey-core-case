from app.domain.event_properties import PatientCreatedProperties
from app.domain.enums import EventName
from app.repositories.in_memory import EventRepository
from app.services.event_service import EventService


def test_event_does_not_contain_patient_pii() -> None:
    repository = EventRepository()
    service = EventService(repository)
    event = service.emit(
        EventName.PATIENT_CREATED,
        "patient-hash",
        PatientCreatedProperties(),
    )

    payload = event.model_dump(mode="json")

    assert "phone" not in payload
    assert "name" not in payload
    assert "birth_date" not in payload
    assert "phone" not in payload["properties"]
    assert "name" not in payload["properties"]
    assert "birth_date" not in payload["properties"]


def test_event_properties_cannot_accept_patient_pii_fields() -> None:
    repository = EventRepository()
    service = EventService(repository)

    event = service.emit(
        EventName.PATIENT_CREATED,
        "patient-hash",
        PatientCreatedProperties(),
    )

    assert event.properties == {}
