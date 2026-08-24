import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.domain.errors import ProtocolTemplateNotFound
from app.domain.models import ProtocolTemplate
from app.protocols.loader import TemplateLoader


def test_loader_returns_protocol_template() -> None:
    template = TemplateLoader().load("phq9")

    assert isinstance(template, ProtocolTemplate)
    assert template.template_id == "phq9"


def test_loader_supports_version_lookup() -> None:
    template = TemplateLoader().load("phq9", version="1.0")

    assert template.version == "1.0"


def test_loader_raises_for_unknown_template() -> None:
    with pytest.raises(ProtocolTemplateNotFound):
        TemplateLoader().load("does_not_exist")


def test_loader_raises_for_unknown_version() -> None:
    with pytest.raises(ProtocolTemplateNotFound):
        TemplateLoader().load("phq9", version="9.9")


def test_loader_does_not_accept_arbitrary_paths() -> None:
    with pytest.raises(ProtocolTemplateNotFound):
        TemplateLoader().load("../../arquivo_secreto")


def test_loader_surfaces_pydantic_validation_errors(tmp_path: Path) -> None:
    invalid_template = {
        "template_id": "invalid",
        "version": "1.0",
        "name": "Invalid",
        "questions": [],
        "skip_rules": [],
    }
    (tmp_path / "invalid.json").write_text(
        json.dumps(invalid_template),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        TemplateLoader(tmp_path).load("invalid")


def test_loader_rejects_unknown_skip_rule_references(tmp_path: Path) -> None:
    invalid_template = {
        "template_id": "invalid_refs",
        "version": "1.0",
        "name": "Invalid refs",
        "questions": [
            {
                "id": "1",
                "text": "Question",
                "type": "likert",
                "options": [{"value": 0, "label": "None"}],
            }
        ],
        "skip_rules": [
            {
                "trigger": {"after_question": "2"},
                "condition": {
                    "operator": "sum",
                    "questions": ["1", "2"],
                    "comparison": "lt",
                    "value": 3,
                },
                "action": "end_block",
            }
        ],
    }
    (tmp_path / "invalid_refs.json").write_text(
        json.dumps(invalid_template),
        encoding="utf-8",
    )

    with pytest.raises(ValidationError):
        TemplateLoader(tmp_path).load("invalid_refs")
