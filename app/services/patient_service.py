from datetime import date

from app.domain.enums import EventName
from app.domain.event_properties import PatientCreatedProperties, TermsAcceptedProperties
from app.domain.models import Patient
from app.repositories.in_memory import PatientRepository
from app.security.hashing import PhoneHasher
from app.services.event_service import EventService


class PatientService:
    def __init__(
        self,
        patient_repository: PatientRepository,
        phone_hasher: PhoneHasher,
        event_service: EventService,
    ) -> None:
        self._patient_repository = patient_repository
        self._phone_hasher = phone_hasher
        self._event_service = event_service

    def create_patient(
        self,
        phone: str,
        name: str,
        birth_date: date,
        sex: str,
        terms_accepted: bool,
    ) -> Patient:
        patient = Patient(
            phone=phone,
            phone_hash=self._phone_hasher.hash(phone),
            name=name,
            birth_date=birth_date,
            sex=sex,
            terms_accepted=terms_accepted,
        )
        self._patient_repository.save(patient)
        self._event_service.emit(
            EventName.PATIENT_CREATED,
            patient.phone_hash,
            PatientCreatedProperties(),
        )
        if patient.terms_accepted:
            self._event_service.emit(
                EventName.TERMS_ACCEPTED,
                patient.phone_hash,
                TermsAcceptedProperties(),
            )
        return patient
