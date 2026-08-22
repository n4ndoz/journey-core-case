from app.security.hashing import PhoneHasher


def test_same_phone_and_salt_produce_same_hash() -> None:
    first = PhoneHasher("salt").hash("+55 (21) 99999-9999")
    second = PhoneHasher("salt").hash("+55 (21) 99999-9999")

    assert first == second


def test_equivalent_phone_formatting_produces_same_hash() -> None:
    hasher = PhoneHasher("salt")

    assert hasher.hash("+55 (21) 99999-9999") == hasher.hash("5521999999999")


def test_different_salts_produce_different_hashes() -> None:
    phone = "+55 (21) 99999-9999"

    assert PhoneHasher("salt-a").hash(phone) != PhoneHasher("salt-b").hash(phone)


def test_cleartext_phone_does_not_appear_in_hash() -> None:
    phone = "+55 (21) 99999-9999"

    assert phone not in PhoneHasher("salt").hash(phone)
