from uuid import UUID

from fastapi import APIRouter

from app.api_schemas import (
    EventResponse,
    FollowupDecisionResponse,
    FollowupEvaluateRequest,
    JourneyResponse,
    PatientCreateRequest,
    PatientResponse,
    ProtocolAnswerRequest,
    ProtocolAnswerResponse,
    ProtocolStartRequest,
    ProtocolStartResponse,
    QuestionOptionResponse,
    QuestionResponse,
    TaskCompletionResponse,
    TaskResponse,
)
from app.dependencies import (
    event_repository,
    followup_service,
    journey_repository,
    journey_service,
    patient_repository,
    patient_service,
    protocol_service,
    template_loader,
)
from app.domain.errors import JourneyNotFound, PatientNotFound
from app.domain.models import ProtocolAnswer, ProtocolSession, ProtocolTemplate, Question

router = APIRouter()


def _question_response(question: Question) -> QuestionResponse:
    return QuestionResponse(
        id=question.id,
        text=question.text,
        options=[
            QuestionOptionResponse(value=option.value, label=option.label)
            for option in question.options
        ],
    )


def _current_question(
    session: ProtocolSession,
    template: ProtocolTemplate,
) -> QuestionResponse:
    question = next(
        question for question in template.questions if question.id == session.current_question_id
    )
    return _question_response(question)


@router.post('/patients', response_model=PatientResponse, status_code=201)
def create_patient(payload: PatientCreateRequest) -> PatientResponse:
    patient = patient_service.create_patient(**payload.model_dump())
    return PatientResponse(
        patient_id=patient.patient_id,
        phone=patient.phone,
        name=patient.name,
        birth_date=patient.birth_date,
        sex=patient.sex,
        terms_accepted=patient.terms_accepted,
    )


@router.post(
    '/patients/{patient_id}/protocols',
    response_model=ProtocolStartResponse,
    status_code=201,
)
def start_protocol(patient_id: UUID, payload: ProtocolStartRequest) -> ProtocolStartResponse:
    session = protocol_service.start_protocol(patient_id, payload.template_id)
    template = template_loader.load(session.template_id, version=session.template_version)
    return ProtocolStartResponse(
        session_id=session.session_id,
        status=session.status,
        prompt=template.prompt or None,
        current_question=_current_question(session, template),
    )


@router.post(
    '/protocol-sessions/{session_id}/answers',
    response_model=ProtocolAnswerResponse,
)
def submit_answer(session_id: UUID, payload: ProtocolAnswerRequest) -> ProtocolAnswerResponse:
    session = protocol_service.submit_answer(
        session_id,
        ProtocolAnswer(question_id=payload.question_id, value=payload.value),
    )

    next_question = None
    if session.current_question_id is not None:
        template = template_loader.load(
            session.template_id,
            version=session.template_version,
        )
        next_question = _current_question(session, template)

    return ProtocolAnswerResponse(
        session_id=session.session_id,
        status=session.status,
        next_question=next_question,
        score=session.score,
        ended_by_skip=session.ended_by_skip,
    )


@router.get('/patients/{patient_id}/journey', response_model=JourneyResponse)
def get_journey(patient_id: UUID) -> JourneyResponse:
    if patient_repository.get(patient_id) is None:
        raise PatientNotFound()
    journey = journey_repository.get_by_patient(patient_id)
    if journey is None:
        raise JourneyNotFound()
    return JourneyResponse(
        journey_id=journey.journey_id,
        status=journey.status,
        objective=journey.objective,
        tasks=[TaskResponse(**task.model_dump()) for task in journey.tasks],
    )


@router.post(
    '/journeys/{journey_id}/tasks/{task_id}/complete',
    response_model=TaskCompletionResponse,
)
def complete_task(journey_id: UUID, task_id: UUID) -> TaskCompletionResponse:
    journey = journey_repository.get(journey_id)
    if journey is None:
        raise JourneyNotFound()
    patient = patient_repository.get(journey.patient_id)
    if patient is None:
        raise PatientNotFound()
    task = journey_service.complete_task(journey_id, task_id, patient.phone_hash)
    return TaskCompletionResponse(
        journey_id=journey_id,
        task_id=task.task_id,
        status=task.status,
    )


@router.post('/followups/evaluate', response_model=FollowupDecisionResponse)
def evaluate_followup(payload: FollowupEvaluateRequest) -> FollowupDecisionResponse:
    decision = followup_service.evaluate(payload.patient_id)
    return FollowupDecisionResponse(**decision.model_dump())


@router.get('/events', response_model=list[EventResponse])
def get_events(patient_id: UUID) -> list[EventResponse]:
    patient = patient_repository.get(patient_id)
    if patient is None:
        raise PatientNotFound()
    return [
        EventResponse(**event.model_dump())
        for event in event_repository.list_by_patient(patient.phone_hash)
    ]
