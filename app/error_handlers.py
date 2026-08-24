from fastapi import Request
from fastapi.responses import JSONResponse

from app.domain.errors import (
    ConsentRequired,
    DomainError,
    InvalidAnswer,
    JourneyNotFound,
    PatientNotFound,
    ProtocolAlreadyCompleted,
    ProtocolNotCompleted,
    ProtocolSessionNotFound,
    ProtocolTemplateNotFound,
    QuestionMismatch,
    TaskAlreadyCompleted,
    TaskNotFound,
    UnsupportedFollowupRule,
    UnsupportedProtocolRule,
)

_ERROR_MAP: dict[type[DomainError], tuple[int, str, str]] = {
    PatientNotFound: (404, "patient_not_found", "Patient not found"),
    ProtocolTemplateNotFound: (404, "protocol_template_not_found", "Protocol template not found"),
    ProtocolSessionNotFound: (404, "protocol_session_not_found", "Protocol session not found"),
    JourneyNotFound: (404, "journey_not_found", "Journey not found"),
    TaskNotFound: (404, "task_not_found", "Task not found"),
    ConsentRequired: (403, "consent_required", "Consent is required"),
    ProtocolAlreadyCompleted: (409, "protocol_already_completed", "Protocol is already completed"),
    TaskAlreadyCompleted: (409, "task_already_completed", "Task is already completed"),
    ProtocolNotCompleted: (409, "protocol_not_completed", "Protocol is not completed"),
    QuestionMismatch: (409, "question_mismatch", "Question does not match current protocol state"),
    InvalidAnswer: (422, "invalid_answer", "Invalid answer"),
    UnsupportedProtocolRule: (500, "internal_error", "Internal server error"),
    UnsupportedFollowupRule: (500, "internal_error", "Internal server error"),
}


async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
    status_code, error, message = _ERROR_MAP.get(
        type(exc),
        (500, "internal_error", "Internal server error"),
    )
    return JSONResponse(
        status_code=status_code,
        content={"error": error, "message": message},
    )
