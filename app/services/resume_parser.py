import json
import os

from groq import APIError, Groq
from pydantic import ValidationError

from app.models.schemas import Resume


def parse_resume_text(text: str) -> Resume:
    """
    Convert already-cleaned resume text into a validated Resume object
    using the Groq hosted LLM.
    """

    if not text.strip():
        raise ValueError("Resume text cannot be empty.")

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
                        "Parse the following resume into the requested "
                        "JSON structure.\n\n"
                        "RESUME TEXT:\n"
                        f"{text}"
                    ),
                },
            ],
        )
    except APIError as error:
        raise ValueError(
            "Groq failed to parse the resume."
        ) from error

    if not response.choices:
        raise ValueError(
            "Groq returned no response choices."
        )

    content = response.choices[0].message.content

    if not content:
        raise ValueError(
            "Groq returned an empty resume-parsing response."
        )

    try:
        parsed_data = json.loads(content)
    except json.JSONDecodeError as error:
        raise ValueError(
            "Groq returned invalid JSON for the resume."
        ) from error

    try:
        return _validate_resume(parsed_data)
    except ValidationError as error:
        raise ValueError(
            "Groq returned data that does not match the Resume schema."
        ) from error


def _build_system_prompt() -> str:
    """
    Instructions given to Groq for structured resume extraction.
    """

    return """
You are a resume information extraction system.

Return only valid JSON.
Do not return Markdown.
Do not return explanations.
Do not use code fences.

Return exactly this structure:

{
  "contact": {
    "name": "string or null",
    "email": "string or null",
    "phone": "string or null",
    "location": "string or null",
    "linkedin": "string or null"
  },
  "summary": "string or null",
  "experience": [
    {
      "title": "string or null",
      "company": "string or null",
      "start_date": "string or null",
      "end_date": "string or null",
      "bullets": ["string"]
    }
  ],
  "education": [
    {
      "degree": "string or null",
      "school": "string or null",
      "start_date": "string or null",
      "end_date": "string or null"
    }
  ],
  "skills": ["string"],
  "projects": [
    {
      "name": "string or null",
      "description": "string or null",
      "bullets": ["string"]
    }
  ],
  "certifications": ["string"],
  "red_flags": ["string"]
}

Rules:

1. Use only facts explicitly present in the resume.
2. Never invent employers, companies, job titles, skills, dates, degrees,
   certifications, achievements, or metrics.
3. Use null when a scalar value is not available.
4. Use an empty list when a section is not present.
5. Preserve the original meaning of experience bullets.
6. Keep separate jobs as separate experience objects.
7. Keep separate projects as separate project objects.
8. Do not put job responsibilities into the skills list.
9. Do not put skills into the certifications list.
10. Do not guess contact information.
11. Keep dates exactly as written when possible.
12. Return valid JSON only.
"""


def _validate_resume(data: dict) -> Resume:
    """
    Validate Groq's dictionary using the project's Resume model.

    Pydantic v2 uses model_validate().
    Pydantic v1 uses parse_obj().
    """

    if hasattr(Resume, "model_validate"):
        return Resume.model_validate(data)

    return Resume.parse_obj(data)