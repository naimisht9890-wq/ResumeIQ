import json
import os

from groq import APIError, Groq
from pydantic import ValidationError

from app.models.schemas import JobDescription


def parse_job_description_text(text: str) -> JobDescription:
    """
    Convert raw job-description text into a validated JobDescription object.
    """

    if not text.strip():
        raise ValueError("Job-description text cannot be empty.")

    api_key = os.getenv("GROQ_API_KEY")

    if not api_key:
        raise ValueError(
            "GROQ_API_KEY is not configured. "
            "Add it to the .env file."
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
            response_format={
                "type": "json_object",
            },
            messages=[
                {
                    "role": "system",
                    "content": _build_system_prompt(),
                },
                {
                    "role": "user",
                    "content": (
                        "Parse the following job description into the "
                        "requested JSON structure.\n\n"
                        "JOB DESCRIPTION:\n"
                        f"{text}"
                    ),
                },
            ],
        )
    except APIError as error:
        raise ValueError(
            "Groq failed to parse the job description."
        ) from error

    if not response.choices:
        raise ValueError(
            "Groq returned no response choices."
        )

    content = response.choices[0].message.content

    if not content:
        raise ValueError(
            "Groq returned an empty job-description response."
        )

    try:
        parsed_data = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError(
            "Groq returned invalid JSON for the job description."
        ) from error

    try:
        return _validate_job_description(parsed_data)
    except ValidationError as error:
        raise ValueError(
            "Groq returned data that does not match the "
            "JobDescription schema."
        ) from error


def _build_system_prompt() -> str:
    """
    Instructions given to Groq for structured job-description extraction.
    """

    return """
You are a job-description information extraction system.

Return only valid JSON.
Do not return Markdown.
Do not return explanations.
Do not use code fences.

Return exactly this structure:

{
  "title": "string or null",
  "company": "string or null",
  "raw_text": "string",
  "required_skills": ["string"],
  "preferred_skills": ["string"],
  "responsibilities": ["string"]
}

Rules:

1. Preserve the complete original job description in raw_text.
2. Extract the job title only when it is explicitly present.
3. Extract the company only when it is explicitly present.
4. Never invent a company, title, skill, or responsibility.
5. Use null for missing title or company.
6. Use an empty list when no skills or responsibilities are found.
7. Put skills required for the role into required_skills.
8. Put useful but non-required skills into preferred_skills.
9. Keep required_skills and preferred_skills separate.
10. Convert responsibilities into short, clear statements.
11. Do not add skills that are not present in the job description.
12. Return valid JSON only.
"""


def _validate_job_description(
    data: dict,
) -> JobDescription:
    """
    Validate Groq's dictionary using the JobDescription model.

    Pydantic v2 uses model_validate().
    Pydantic v1 uses parse_obj().
    """

    if hasattr(JobDescription, "model_validate"):
        return JobDescription.model_validate(data)

    return JobDescription.parse_obj(data)