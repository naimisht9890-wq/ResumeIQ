import json
from pathlib import Path
from typing import Any


KNOWLEDGE_FILE = (
    Path(__file__).resolve().parents[2]
    / "knowledge"
    / "resume_best_practices.json"
)


def load_knowledge() -> list[dict[str, Any]]:
    """
    Load curated resume best-practice rules from disk.
    """

    if not KNOWLEDGE_FILE.exists():
        raise RuntimeError(
            f"Knowledge file was not found: {KNOWLEDGE_FILE}"
        )

    try:
        with KNOWLEDGE_FILE.open(
            "r",
            encoding="utf-8",
        ) as file:
            data = json.load(file)
    except json.JSONDecodeError as error:
        raise RuntimeError(
            "The resume best-practices knowledge file contains invalid JSON."
        ) from error

    if not isinstance(data, list):
        raise RuntimeError(
            "The resume best-practices knowledge file must contain a list."
        )

    return data


def retrieve_rule(category: str) -> dict[str, Any]:
    """
    Retrieve the best-practice rule for a feedback category.
    """

    rules = load_knowledge()

    for rule in rules:
        if rule.get("category") == category:
            return rule

    raise ValueError(
        f"No best-practice rule exists for category: {category}"
    )