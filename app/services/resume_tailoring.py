import json
import os

from groq import APIError, Groq
from pydantic import ValidationError

from app.models.schemas import (
    TailorResumeRequest,
    TailorResumeResult,
)
from app.services.knowledge_retriever import retrieve_rule
from app.services.skill_gap_analysis import analyze_skill_gap


def tailor_resume(
    request: TailorResumeRequest,
) -> TailorResumeResult:
    """
    Generate reviewable resume edits grounded in the original resume.
    """

    skill_gap = analyze_skill_gap(request)
    rules = [
        retrieve_rule("keywords"),
        retrieve_rule("experience"),
        retrieve_rule("quantification"),
    ]

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError(
            "GROQ_API_KEY is not configured. Add it to the .env file."
        )

    client = Groq(
        api_key=api_key,
    )
    model = os.getenv(
        "GROQ_MODEL",
        "openai/gpt-oss-20b",
    )

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
                        request,
                        skill_gap,
                        rules,
                    ),
                },
            ],
        )
    except APIError as error:
        raise ValueError(
            "Groq failed to generate resume tailoring suggestions."
        ) from error

    if not response.choices:
        raise ValueError(
            "Groq returned no response choices for resume tailoring."
        )

    content = response.choices[0].message.content

    if not content:
        raise ValueError(
            "Groq returned an empty resume tailoring response."
        )

    try:
        parsed_data = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError(
            "Groq returned invalid JSON for resume tailoring."
        ) from error

    try:
        result = _validate_result(parsed_data)
    except ValidationError as error:
        raise ValueError(
            "Groq returned data that does not match the "
            "TailorResumeResult schema."
        ) from error

    _validate_change_safety(
        result,
        request,
    )
    return result


def _build_system_prompt() -> str:
    return """
You are a resume tailoring assistant.

Return only valid JSON. Do not return Markdown or code fences.

Return exactly:
{
  "changes": [
    {
      "section": "experience or summary or project",
      "original_text": "text copied exactly from the resume",
      "suggested_text": "rewritten text",
      "reason": "short explanation",
      "supported_by_resume": true
    }
  ],
  "warnings": ["string"]
}

Rules:
1. Suggest edits only; never return a complete replacement resume.
2. original_text must be copied exactly from the supplied resume.
3. suggested_text may improve clarity, action verbs, and job relevance.
4. Never invent employers, job titles, dates, skills, metrics, users,
   technologies, responsibilities, or achievements.
5. Do not add a missing skill unless the original resume already supports it.
6. Set supported_by_resume to true only when the suggestion preserves
   the original factual meaning.
7. If a requested job skill is missing, add a warning instead of inventing
   experience with that skill.
8. Keep suggestions concise and suitable for a resume.
"""


def _build_user_prompt(
    request: TailorResumeRequest,
    skill_gap,
    rules: list[dict],
) -> str:
    if hasattr(request, "model_dump"):
        request_data = request.model_dump(mode="json")
        gap_data = skill_gap.model_dump(mode="json")
    else:
        request_data = request.dict()
        gap_data = skill_gap.dict()

    return (
        "Create reviewable tailoring suggestions.\n\n"
        "RESUME AND JOB DESCRIPTION:\n"
        f"{json.dumps(request_data, indent=2)}\n\n"
        "DETERMINISTIC SKILL GAP:\n"
        f"{json.dumps(gap_data, indent=2)}\n\n"
        "RETRIEVED BEST-PRACTICE RULES:\n"
        f"{json.dumps(rules, indent=2)}"
    )


def _validate_result(data: dict) -> TailorResumeResult:
    if hasattr(TailorResumeResult, "model_validate"):
        return TailorResumeResult.model_validate(data)

    return TailorResumeResult.parse_obj(data)


def _validate_change_safety(
    result: TailorResumeResult,
    request: TailorResumeRequest,
) -> None:
    source_texts = _resume_source_texts(request)

    for change in result.changes:
        if not change.original_text.strip():
            raise ValueError(
                "Groq returned a tailoring change without original text."
            )

        if not change.suggested_text.strip():
            raise ValueError(
                "Groq returned a tailoring change without suggested text."
            )

        if change.original_text not in source_texts:
            raise ValueError(
                "Groq returned original text that was not found in "
                "the supplied resume."
            )


def _resume_source_texts(
    request: TailorResumeRequest,
) -> set[str]:
    resume = request.resume
    source_texts: set[str] = set()

    if resume.summary:
        source_texts.add(resume.summary)

    for item in resume.experience:
        source_texts.update(item.bullets)

    for project in resume.projects:
        if project.name:
            source_texts.add(project.name)
        if project.description:
            source_texts.add(project.description)
        source_texts.update(project.bullets)

    return source_texts
