import hashlib
import os
import re


class PhoneHasher:
    def __init__(self, salt: str | None = None) -> None:
        self._salt = salt if salt is not None else os.getenv("PHONE_HASH_SALT", "")

    def normalize(self, phone: str) -> str:
        return re.sub(r"\D", "", phone)

    def hash(self, phone: str) -> str:
        normalized_phone = self.normalize(phone)
        payload = f"{self._salt}{normalized_phone}".encode("utf-8")
        return hashlib.sha256(payload).hexdigest()
