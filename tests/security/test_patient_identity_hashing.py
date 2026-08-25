import hashlib
from uuid import UUID

from app.security.hashing import PhoneHasher


def test_phone_hash_algorithm_remains_unchanged() -> None:
    salt = "test-salt"
    phone = "+55 (11) 98888-7777"
    normalized = "5511988887777"

    expected = hashlib.sha256(f"{salt}{normalized}".encode("utf-8")).hexdigest()

    assert PhoneHasher(salt=salt).hash(phone) == expected


def test_patient_id_hash_uses_separate_domain_payload() -> None:
    salt = "test-salt"
    patient_id = UUID("00000000-0000-0000-0000-000000000123")

    expected = hashlib.sha256(
        f"{salt}patient:{patient_id}".encode("utf-8")
    ).hexdigest()
    hasher = PhoneHasher(salt=salt)

    assert hasher.hash_patient_id(patient_id) == expected
    assert hasher.hash_patient_id(patient_id) != hasher.hash(str(patient_id))
