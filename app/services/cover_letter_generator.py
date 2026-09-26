import json
import os

from groq import APIError, Groq
from pydantic import ValidationError

from app.models.schemas import (
    CoverLetterRequest,
    CoverLetterResult,
)
from app.services.knowledge_retriever import (
    citations_for_context,
    retrieve_context,
)
from app.services.skill_gap_analysis import analyze_skill_gap


def generate_cover_letter(
    request: CoverLetterRequest,
) -> CoverLetterResult:
    """
    Generate a grounded cover-letter draft from validated input data.
    """

    skill_gap = analyze_skill_gap(request)
    query = " ".join(
        [
            request.job_description.raw_text,
            *request.job_description.required_skills,
            *request.job_description.preferred_skills,
            request.resume.summary or "",
            *request.resume.skills,
            *request.resume.certifications,
        ]
    )
    rules = retrieve_context(
        query,
        ["cover_letter", "keywords"],
        top_k=4,
    )

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError(
            "GROQ_API_KEY is not configured. Add it to the .env file."
        )

    client = Groq(api_key=api_key)
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
            "Groq failed to generate the cover letter."
        ) from error

    if not response.choices:
        raise ValueError(
            "Groq returned no response choices for the cover letter."
        )

    content = response.choices[0].message.content

    if not content:
        raise ValueError(
            "Groq returned an empty cover-letter response."
        )

    try:
        parsed_data = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError(
            "Groq returned invalid JSON for the cover letter."
        ) from error

    try:
        result = _validate_result(parsed_data)
    except ValidationError as error:
        raise ValueError(
            "Groq returned data that does not match the "
            "CoverLetterResult schema."
        ) from error

    _validate_fact_references(result, request)
    result.citations = citations_for_context(rules)
    return result


def _build_system_prompt() -> str:
    return """
You are a grounded cover-letter writing assistant.

Return only valid JSON. Do not return Markdown or code fences.

Return exactly:
{
  "draft": "cover letter text",
  "resume_facts_used": ["exact text copied from the resume"],
  "warnings": ["string"]
}

Rules:
1. Write a concise professional cover letter of 3 to 5 paragraphs.
2. Use only facts explicitly present in the supplied resume.
3. Do not invent employers, job titles, dates, skills, metrics,
   responsibilities, achievements, or personal motivations.
4. Do not claim that a missing job skill is present.
5. If important information is missing, mention it in warnings.
6. resume_facts_used must contain exact text copied from the resume.
7. Do not include placeholders such as [Company Name] or [Your Name].
8. Keep the tone specific to the supplied job description.
"""


def _build_user_prompt(
    request: CoverLetterRequest,
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
        "Create a grounded cover-letter draft.\n\n"
        "RESUME AND JOB DESCRIPTION:\n"
        f"{json.dumps(request_data, indent=2)}\n\n"
        "DETERMINISTIC SKILL GAP:\n"
        f"{json.dumps(gap_data, indent=2)}\n\n"
        "RETRIEVED BEST-PRACTICE RULES:\n"
        f"{json.dumps(rules, indent=2)}"
    )


def _validate_result(data: dict) -> CoverLetterResult:
    if hasattr(CoverLetterResult, "model_validate"):
        return CoverLetterResult.model_validate(data)

    return CoverLetterResult.parse_obj(data)


def _validate_fact_references(
    result: CoverLetterResult,
    request: CoverLetterRequest,
) -> None:
    source_texts = _resume_source_texts(request)

    if not result.draft.strip():
        raise ValueError(
            "Groq returned an empty cover-letter draft."
        )

    for fact in result.resume_facts_used:
        if fact not in source_texts:
            raise ValueError(
                "Groq referenced a resume fact that was not found in "
                "the supplied resume."
            )


def _resume_source_texts(
    request: CoverLetterRequest,
) -> set[str]:
    resume = request.resume
    source_texts: set[str] = set()

    if resume.summary:
        source_texts.add(resume.summary)

    source_texts.update(resume.skills)
    source_texts.update(resume.certifications)

    for item in resume.experience:
        if item.title:
            source_texts.add(item.title)
        if item.company:
            source_texts.add(item.company)
        source_texts.update(item.bullets)

    for project in resume.projects:
        if project.name:
            source_texts.add(project.name)
        if project.description:
            source_texts.add(project.description)
        source_texts.update(project.bullets)

    return source_texts
