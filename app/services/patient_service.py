from datetime import date
from uuid import uuid4

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
        patient_id = uuid4()
        patient = Patient(
            patient_id=patient_id,
            patient_id_hash=self._phone_hasher.hash_patient_id(patient_id),
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
            patient.patient_id_hash,
            PatientCreatedProperties(),
        )
        if patient.terms_accepted:
            self._event_service.emit(
                EventName.TERMS_ACCEPTED,
                patient.patient_id_hash,
                TermsAcceptedProperties(),
            )
        return patient
