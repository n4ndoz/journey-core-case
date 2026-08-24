import json
import re
from pathlib import Path

from app.followups.models import FollowupRules


_RULESET_NAME_PATTERN = re.compile(r"^[A-Za-z0-9_-]+$")


class FollowupRulesLoader:
    def __init__(self, rules_dir: Path | None = None) -> None:
        self._rules_dir = rules_dir or Path(__file__).parent / "rules"

    def load(self, ruleset_name: str = "default") -> FollowupRules:
        if not _RULESET_NAME_PATTERN.fullmatch(ruleset_name):
            raise FileNotFoundError(ruleset_name)

        rules_path = self._rules_dir / f"{ruleset_name}.json"
        if not rules_path.is_file():
            raise FileNotFoundError(ruleset_name)

        raw_rules = json.loads(rules_path.read_text(encoding="utf-8"))
        return FollowupRules.model_validate(raw_rules)
