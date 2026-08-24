from dotenv import load_dotenv


def test_external_phone_hash_salt_is_not_overridden_by_dotenv(monkeypatch, tmp_path) -> None:
    dotenv_path = tmp_path / ".env"
    dotenv_path.write_text("PHONE_HASH_SALT=from-dotenv\n", encoding="utf-8")
    monkeypatch.setenv("PHONE_HASH_SALT", "external-salt")

    load_dotenv(dotenv_path=dotenv_path)

    import os

    assert os.environ["PHONE_HASH_SALT"] == "external-salt"
