import re

from app.models.schemas import (
    FeedbackItem,
    JobDescription,
    Resume,
    StrengthsWeaknessesRequest,
    StrengthsWeaknessesResult,
)
from app.services.knowledge_retriever import retrieve_rule

from app.models.schemas import (
    FeedbackItem,
    JobDescription,
    Resume,
    StrengthsWeaknessesRequest,
    StrengthsWeaknessesResult,
)





NUMBER_PATTERN = re.compile(
    r"(?<!\w)(?:\d+(?:[.,]\d+)?\s*%?)(?!\w)"
)

ACTION_VERBS = {
    "achieved",
    "automated",
    "built",
    "created",
    "decreased",
    "delivered",
    "designed",
    "developed",
    "improved",
    "increased",
    "implemented",
    "launched",
    "managed",
    "migrated",
    "optimized",
    "reduced",
    "resolved",
    "scaled",
}


def analyze_strengths_weaknesses(
    request: StrengthsWeaknessesRequest,
) -> StrengthsWeaknessesResult:
    """
    Analyze a resume using deterministic checks and retrieved
    best-practice rules.
    """

    resume = request.resume
    job_description = request.job_description

    strengths: list[FeedbackItem] = []
    weaknesses: list[FeedbackItem] = []

    if _has_contact_information(resume):
        strengths.append(
            _feedback_from_rule(
                category="contact",
                point="Contact information is present.",
                evidence=_contact_evidence(resume),
            )
        )
    else:
        weaknesses.append(
            _feedback_from_rule(
                category="contact",
                point="Contact information is incomplete or missing.",
                suggestion=(
                    "Add a name and at least one reliable contact method."
                ),
            )
        )

    if resume.summary:
        strengths.append(
            _feedback_from_rule(
                category="summary",
                point="A professional summary is present.",
                evidence=resume.summary,
            )
        )
    else:
        weaknesses.append(
            _feedback_from_rule(
                category="summary",
                point="The resume does not contain a professional summary.",
                suggestion=(
                    "Add a concise summary describing your role, "
                    "experience, and strongest relevant skills."
                ),
            )
        )

    bullets = _all_bullets(resume)

    if resume.experience:
        if bullets:
            strengths.append(
                _feedback_from_rule(
                    category="experience",
                    point="Work experience includes detailed bullets.",
                    evidence=(
                        f"{len(resume.experience)} experience item(s) "
                        f"with {len(bullets)} bullet(s)."
                    ),
                )
            )
        else:
            weaknesses.append(
                _feedback_from_rule(
                    category="experience",
                    point="Experience entries do not contain bullet points.",
                    suggestion=(
                        "Describe responsibilities and achievements using "
                        "short action-oriented bullets."
                    ),
                )
            )
    else:
        weaknesses.append(
            _feedback_from_rule(
                category="experience",
                point="No work experience was detected.",
                suggestion=(
                    "Add relevant employment, internships, freelance work, "
                    "or practical experience when applicable."
                ),
            )
        )

    quantified_bullets = [
        bullet
        for bullet in bullets
        if NUMBER_PATTERN.search(bullet)
    ]

    if quantified_bullets:
        strengths.append(
            _feedback_from_rule(
                category="quantification",
                point="Some bullets contain measurable information.",
                evidence=quantified_bullets[0],
            )
        )
    elif bullets:
        weaknesses.append(
            _feedback_from_rule(
                category="quantification",
                point="The experience bullets lack measurable outcomes.",
                suggestion=(
                    "Add numbers, percentages, time saved, users served, "
                    "revenue, scale, or other measurable results."
                ),
            )
        )

    action_bullets = [
        bullet
        for bullet in bullets
        if _starts_with_action_verb(bullet)
    ]

    if bullets and len(action_bullets) >= len(bullets) / 2:
        strengths.append(
            _feedback_from_rule(
                category="experience",
                point="Many bullets use action-oriented language.",
                evidence=action_bullets[0],
            )
        )
    elif bullets:
        weaknesses.append(
            _feedback_from_rule(
                category="experience",
                point="Many bullets do not begin with strong action verbs.",
                suggestion=(
                    "Begin bullets with verbs such as built, improved, "
                    "designed, automated, reduced, or delivered."
                ),
            )
        )

    if resume.skills:
        strengths.append(
            _feedback_from_rule(
                category="skills",
                point="A skills section is present.",
                evidence=", ".join(resume.skills[:8]),
            )
        )
    else:
        weaknesses.append(
            _feedback_from_rule(
                category="skills",
                point="No skills were detected.",
                suggestion=(
                    "Add a focused list of relevant technical and "
                    "professional skills."
                ),
            )
        )

    if job_description is not None:
        _add_keyword_feedback(
            resume=resume,
            job_description=job_description,
            strengths=strengths,
            weaknesses=weaknesses,
        )

    if resume.projects:
        strengths.append(
            _feedback_from_rule(
                category="projects",
                point="The resume includes practical projects.",
                evidence=resume.projects[0].name,
            )
        )

    return StrengthsWeaknessesResult(
        strengths=strengths,
        weaknesses=weaknesses,
    )


def _add_keyword_feedback(
    resume: Resume,
    job_description: JobDescription,
    strengths: list[FeedbackItem],
    weaknesses: list[FeedbackItem],
) -> None:
    resume_text = _resume_text(resume).lower()

    target_skills = (
        job_description.required_skills
        + job_description.preferred_skills
    )

    matched = [
        skill
        for skill in target_skills
        if skill.lower() in resume_text
    ]

    missing = [
        skill
        for skill in target_skills
        if skill.lower() not in resume_text
    ]

    if matched:
        strengths.append(
            _feedback_from_rule(
                category="keywords",
                point="The resume contains some target job skills.",
                evidence=", ".join(matched),
            )
        )

    if missing:
        weaknesses.append(
            _feedback_from_rule(
                category="keywords",
                point="Some target job skills were not found.",
                evidence=", ".join(missing),
                suggestion=(
                    "Add a skill only if it is genuinely supported by "
                    "your experience."
                ),
            )
        )


def _feedback_from_rule(
    category: str,
    point: str,
    evidence: str | None = None,
    suggestion: str | None = None,
) -> FeedbackItem:
    """
    Create feedback using a retrieved best-practice rule.
    """

    rule = _retrieve_rule(category)

    grounded_suggestion = suggestion

    if grounded_suggestion is None:
        grounded_suggestion = rule["text"]

    return FeedbackItem(
        section=category,
        point=point,
        evidence=evidence,
        suggestion=grounded_suggestion,
    )

def _retrieve_rule(category: str) -> dict:
    """
    Retrieve a curated rule from the external knowledge base.
    """

    return retrieve_rule(category)


def _has_contact_information(resume: Resume) -> bool:
    return bool(
        resume.contact.name
        or resume.contact.email
        or resume.contact.phone
        or resume.contact.linkedin
    )


def _contact_evidence(resume: Resume) -> str:
    fields: list[str] = []

    if resume.contact.name:
        fields.append("name")

    if resume.contact.email:
        fields.append("email")

    if resume.contact.phone:
        fields.append("phone")

    if resume.contact.linkedin:
        fields.append("LinkedIn")

    return "Available fields: " + ", ".join(fields)


def _all_bullets(resume: Resume) -> list[str]:
    experience_bullets = [
        bullet
        for item in resume.experience
        for bullet in item.bullets
    ]

    project_bullets = [
        bullet
        for project in resume.projects
        for bullet in project.bullets
    ]

    return experience_bullets + project_bullets


def _starts_with_action_verb(bullet: str) -> bool:
    first_word = bullet.strip().split(" ", 1)[0].lower()
    first_word = first_word.strip("-•*.,:;")
    return first_word in ACTION_VERBS


def _resume_text(resume: Resume) -> str:
    values: list[str] = []

    if resume.summary:
        values.append(resume.summary)

    values.extend(resume.skills)

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