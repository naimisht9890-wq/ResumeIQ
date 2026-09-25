import json
import os

from groq import APIError, Groq
from pydantic import ValidationError

from app.models.schemas import (
    StrengthsWeaknessesRequest,
    StrengthsWeaknessesResult,
)
from app.services.feedback_analyzer import (
    analyze_strengths_weaknesses,
)
from app.services.knowledge_retriever import retrieve_rule


def generate_grounded_feedback(
    request: StrengthsWeaknessesRequest,
) -> StrengthsWeaknessesResult:
    """
    Generate grounded feedback using deterministic findings and Groq.

    Python identifies the findings. Groq only improves their wording.
    """

    deterministic_result = analyze_strengths_weaknesses(request)
    categories = _get_feedback_categories(deterministic_result)
    retrieved_rules = [
        retrieve_rule(category)
        for category in categories
    ]

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError(
            "GROQ_API_KEY is not configured. Add it to the .env file."
        )

    model = os.getenv(
        "GROQ_MODEL",
        "openai/gpt-oss-20b",
    )
    client = Groq(api_key=api_key)

    try:
        response = client.chat.completions.create(
            model=model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {
                    "role": "system",
                    "content": _build_system_prompt(),
                },
                {
                    "role": "user",
                    "content": _build_user_prompt(
                        deterministic_result,
                        retrieved_rules,
                    ),
                },
            ],
        )
    except APIError as error:
        raise ValueError(
            "Groq failed to generate grounded resume feedback."
        ) from error

    if not response.choices:
        raise ValueError(
            "Groq returned no response choices for resume feedback."
        )

    content = response.choices[0].message.content

    if not content:
        raise ValueError(
            "Groq returned an empty resume feedback response."
        )

    try:
        parsed_data = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError(
            "Groq returned invalid JSON for resume feedback."
        ) from error

    try:
        return _validate_feedback(parsed_data)
    except ValidationError as error:
        raise ValueError(
            "Groq returned data that does not match the "
            "StrengthsWeaknessesResult schema."
        ) from error


def _get_feedback_categories(
    result: StrengthsWeaknessesResult,
) -> list[str]:
    """Return unique feedback categories in stable order."""

    categories: list[str] = []

    for item in result.strengths + result.weaknesses:
        if item.section not in categories:
            categories.append(item.section)

    return categories


def _build_system_prompt() -> str:
    """Keep Groq grounded in deterministic findings."""

    return """
You are a resume feedback explanation system.

Return only valid JSON.
Do not return Markdown, code fences, or text outside the JSON object.

Return exactly this structure:

{
  "strengths": [
    {
      "section": "string",
      "point": "string",
      "evidence": "string or null",
      "suggestion": "string or null"
    }
  ],
  "weaknesses": [
    {
      "section": "string",
      "point": "string",
      "evidence": "string or null",
      "suggestion": "string or null"
    }
  ]
}

Rules:
1. Preserve the same number of strengths and weaknesses.
2. Preserve every section value.
3. Preserve the meaning of every point.
4. Do not create new strengths or weaknesses.
5. Do not invent resume facts, skills, employers, metrics, or achievements.
6. Do not change evidence into a new claim.
7. Use only the deterministic findings and retrieved rules provided.
8. Make suggestions practical and concise.
9. Use retrieved rules to improve wording, not to introduce unsupported facts.
10. Keep the result valid JSON.
"""


def _build_user_prompt(
    deterministic_result: StrengthsWeaknessesResult,
    retrieved_rules: list[dict],
) -> str:
    """Build the grounded context sent to Groq."""

    if hasattr(deterministic_result, "model_dump"):
        findings = deterministic_result.model_dump(mode="json")
    else:
        findings = deterministic_result.dict()

    return (
        "Rewrite the deterministic resume feedback using the relevant "
        "best-practice rules.\n\n"
        "DETERMINISTIC FINDINGS:\n"
        f"{json.dumps(findings, indent=2)}\n\n"
        "RETRIEVED BEST-PRACTICE RULES:\n"
        f"{json.dumps(retrieved_rules, indent=2)}"
    )


def _validate_feedback(
    data: dict,
) -> StrengthsWeaknessesResult:
    """Validate Groq output with the existing Pydantic schema."""

    if hasattr(StrengthsWeaknessesResult, "model_validate"):
        return StrengthsWeaknessesResult.model_validate(data)

    return StrengthsWeaknessesResult.parse_obj(data)
