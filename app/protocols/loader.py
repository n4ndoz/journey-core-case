import json
import re
from pathlib import Path

from app.domain.errors import ProtocolTemplateNotFound
from app.domain.models import ProtocolTemplate


_TEMPLATE_ID_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class TemplateLoader:
    def __init__(self, templates_dir: Path | None = None) -> None:
        self._templates_dir = templates_dir or Path(__file__).parent / "templates"

    def load(self, template_id: str, version: str | None = None) -> ProtocolTemplate:
        if not _TEMPLATE_ID_PATTERN.fullmatch(template_id):
            raise ProtocolTemplateNotFound(template_id)

        template_path = self._templates_dir / f"{template_id}.json"
        if not template_path.is_file():
            raise ProtocolTemplateNotFound(template_id)

        raw_template = json.loads(template_path.read_text(encoding="utf-8"))
        template = ProtocolTemplate.model_validate(raw_template)

        if template.template_id != template_id:
            raise ValueError("template_id does not match template filename")

        if version is not None and template.version != version:
            raise ProtocolTemplateNotFound(f"{template_id}:{version}")

        return template
