import hashlib
import os
import re
from uuid import UUID


class PhoneHasher:
    def __init__(self, salt: str | None = None) -> None:
        resolved_salt = salt if salt is not None else os.getenv("PHONE_HASH_SALT")
        if not resolved_salt:
            raise ValueError("PHONE_HASH_SALT must be configured")
        self._salt = resolved_salt

    def normalize(self, phone: str) -> str:
        return re.sub(r"\D", "", phone)

    def hash(self, phone: str) -> str:
        normalized_phone = self.normalize(phone)
        payload = f"{self._salt}{normalized_phone}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()

    def hash_patient_id(self, patient_id: UUID) -> str:
        payload = f"{self._salt}patient:{patient_id}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
