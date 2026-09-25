import re
import unicodedata

from app.models.schemas import Resume


SKILL_ALIASES = {
    "nlp": "natural language processing",
    "natural language processing": "natural language processing",
    "sklearn": "scikit learn",
    "scikit learn": "scikit learn",
    "scikit-learn": "scikit learn",
    "js": "javascript",
    "javascript": "javascript",
    "ts": "typescript",
    "typescript": "typescript",
    "py": "python",
    "python": "python",
    "postgres": "postgresql",
    "postgresql": "postgresql",
    "mongo": "mongodb",
    "mongodb": "mongodb",
    "k8s": "kubernetes",
    "kubernetes": "kubernetes",
    "aws": "amazon web services",
    "amazon web services": "amazon web services",
    "gcp": "google cloud platform",
    "google cloud platform": "google cloud platform",
    "azure": "microsoft azure",
    "microsoft azure": "microsoft azure",
}


def canonical_skill(skill: str) -> str:
    """
    Convert a skill or alias to one canonical form.
    """

    normalized = normalize_text(skill)

    return SKILL_ALIASES.get(
        normalized,
        normalized,
    )


def unique_canonical_skills(
    skills: list[str],
) -> list[str]:
    """
    Normalize skills and remove duplicates while preserving order.
    """

    result: list[str] = []

    for skill in skills:
        canonical = canonical_skill(skill)

        if canonical and canonical not in result:
            result.append(canonical)

    return result


def normalize_text(value: str) -> str:
    """
    Normalize case, accents, hyphens, and whitespace.
    """

    normalized = unicodedata.normalize(
        "NFKD",
        value,
    ).lower()

    normalized = normalized.replace(
        "-",
        " ",
    )

    return " ".join(normalized.split())


def resume_search_text(resume: Resume) -> str:
    """
    Build searchable text from resume sections.
    """

    values: list[str] = [
        canonical_skill(skill)
        for skill in resume.skills
    ]

    if resume.summary:
        values.append(resume.summary)

    for item in resume.experience:
        values.extend(
            value
            for value in [
                item.title,
                item.company,
                *item.bullets,
            ]
            if value
        )

    for project in resume.projects:
        values.extend(
            value
            for value in [
                project.name,
                project.description,
                *project.bullets,
            ]
            if value
        )

    return " ".join(values)


def contains_skill(
    resume: Resume,
    resume_text: str,
    target: str,
) -> bool:
    """
    Check whether a canonical skill appears in the resume.
    """

    if contains_term(resume_text, target):
        return True

    aliases = [
        alias
        for alias, canonical in SKILL_ALIASES.items()
        if canonical == target
    ]

    if any(
        contains_term(resume_text, alias)
        for alias in aliases
    ):
        return True

    return any(
        canonical_skill(skill) == target
        for skill in resume.skills
    )


def contains_term(
    text: str,
    term: str,
) -> bool:
    """
    Match a complete term instead of a substring.
    """

    normalized_text = normalize_text(text)
    normalized_term = normalize_text(term)

    return re.search(
        rf"(?<!\w){re.escape(normalized_term)}(?!\w)",
        normalized_text,
    ) is not None