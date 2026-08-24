from uuid import UUID

from app.domain.enums import EventName, JourneyStatus, ProtocolSessionStatus, TaskStatus
from app.domain.errors import (
    JourneyNotFound,
    ProtocolNotCompleted,
    TaskAlreadyCompleted,
    TaskNotFound,
)
from app.domain.event_properties import JourneyCreatedProperties, TaskCompletedProperties
from app.domain.models import Journey, ProtocolSession, Task
from app.repositories.in_memory import JourneyRepository
from app.services.event_service import EventService


class JourneyService:
    OBJECTIVE = "Acompanhamento após protocolo clínico"
    INITIAL_TASK_TITLE = "Realizar acompanhamento"

    def __init__(
        self,
        journey_repository: JourneyRepository,
        event_service: EventService,
    ) -> None:
        self._journey_repository = journey_repository
        self._event_service = event_service

    def create_journey(
        self,
        patient_id: UUID,
        patient_id_hash: str,
        protocol_session: ProtocolSession,
    ) -> Journey:
        if protocol_session.status != ProtocolSessionStatus.COMPLETED:
            raise ProtocolNotCompleted()

        journey = Journey(
            patient_id=patient_id,
            status=JourneyStatus.IN_PROGRESS,
            objective=self.OBJECTIVE,
            tasks=[
                Task(
                    title=self.INITIAL_TASK_TITLE,
                    status=TaskStatus.IN_PROGRESS,
                )
            ],
        )
        self._journey_repository.save(journey)
        self._event_service.emit(
            EventName.JOURNEY_CREATED,
            patient_id_hash,
            JourneyCreatedProperties(
                journey_id=journey.journey_id,
                objective=journey.objective,
            ),
        )
        return journey

    def complete_task(
        self,
        journey_id: UUID,
        task_id: UUID,
        patient_id_hash: str,
    ) -> Task:
        journey = self._journey_repository.get(journey_id)
        if journey is None:
            raise JourneyNotFound()

        task = next((item for item in journey.tasks if item.task_id == task_id), None)
        if task is None:
            raise TaskNotFound()
        if task.status == TaskStatus.COMPLETED:
            raise TaskAlreadyCompleted()

        task.status = TaskStatus.COMPLETED
        self._journey_repository.save(journey)
        self._event_service.emit(
            EventName.TASK_COMPLETED,
            patient_id_hash,
            TaskCompletedProperties(
                journey_id=journey.journey_id,
                task_id=task.task_id,
            ),
        )
        return task
