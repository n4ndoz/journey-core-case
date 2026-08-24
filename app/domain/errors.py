class DomainError(Exception):
    """Base class for domain errors."""


class PatientNotFound(DomainError):
    pass


class ConsentRequired(DomainError):
    pass


class ProtocolTemplateNotFound(DomainError):
    pass


class ProtocolSessionNotFound(DomainError):
    pass


class ProtocolAlreadyCompleted(DomainError):
    pass


class ProtocolNotCompleted(DomainError):
    pass


class InvalidAnswer(DomainError):
    pass


class QuestionMismatch(DomainError):
    pass


class UnsupportedProtocolRule(DomainError):
    pass


class UnsupportedFollowupRule(DomainError):
    pass


class JourneyNotFound(DomainError):
    pass


class TaskNotFound(DomainError):
    pass


class TaskAlreadyCompleted(DomainError):
    pass
