from uuid import UUID

from app.domain.models import Event, Journey, Patient, ProtocolSession


class PatientRepository:
    def __init__(self) -> None:
        self._patients: dict[UUID, Patient] = {}

    def save(self, patient: Patient) -> None:
        self._patients[patient.patient_id] = patient

    def get(self, patient_id: UUID) -> Patient | None:
        return self._patients.get(patient_id)


class ProtocolRepository:
    def __init__(self) -> None:
        self._sessions: dict[UUID, ProtocolSession] = {}

    def save(self, session: ProtocolSession) -> None:
        self._sessions[session.session_id] = session

    def get(self, session_id: UUID) -> ProtocolSession | None:
        return self._sessions.get(session_id)


class JourneyRepository:
    def __init__(self) -> None:
        self._journeys: dict[UUID, Journey] = {}

    def save(self, journey: Journey) -> None:
        self._journeys[journey.journey_id] = journey

    def get(self, journey_id: UUID) -> Journey | None:
        return self._journeys.get(journey_id)

    def get_by_patient(self, patient_id: UUID) -> Journey | None:
        return next(
            (journey for journey in self._journeys.values() if journey.patient_id == patient_id),
            None,
        )


class EventRepository:
    def __init__(self) -> None:
        self._events: list[Event] = []

    def append(self, event: Event) -> None:
        self._events.append(event)

    def list_by_patient(self, patient_id_hash: str) -> list[Event]:
        return [event for event in self._events if event.patient_id_hash == patient_id_hash]

    def list_all(self) -> list[Event]:
        return list(self._events)
