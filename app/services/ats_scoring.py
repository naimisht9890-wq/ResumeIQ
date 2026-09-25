import re

from app.services.skill_matching import (
    contains_skill,
    normalize_text,
    resume_search_text,
    unique_canonical_skills,
)

from app.models.schemas import (
    ATSScoreRequest,
    ATSScoreResult,
    Citation,
    Resume,
    ScoreBreakdown,
)


FORMAT_RULES_SOURCE = "deterministic_ats_rules"

ACTION_VERBS = {
    "achieved", "automated", "built", "created", "decreased", "delivered",
    "designed", "developed", "drove", "enabled", "engineered", "generated",
    "implemented", "improved", "increased", "launched", "led", "managed",
    "migrated", "optimized", "reduced", "resolved", "scaled", "streamlined",
}
IMPACT_WORDS = {
    "accuracy", "cost", "errors", "latency", "performance", "quality",
    "revenue", "retention", "response", "reliability", "time", "throughput",
}
METRIC_PATTERN = re.compile(
    r"(?ix)(?<!\w)(?:"
    r"\d+(?:[.,]\d+)?\s*%"
    r"|\$?\d+(?:[.,]\d+)?\s*(?:k|m|b|hours?|days?|weeks?|months?|years?)"
    r"|\$?\d+(?:[.,]\d+)?"
    r")(?!\w)"
)
WORD_PATTERN = re.compile(r"[a-z0-9]+")
SENTENCE_END_PATTERN = re.compile(r"[.!?]")


def calculate_ats_score(request: ATSScoreRequest) -> ATSScoreResult:
    """Calculate a reproducible, explainable ATS score from resume data."""

    citations: list[Citation] = []
    resume = request.resume
    breakdown = ScoreBreakdown(
        format_compliance=_score_format(resume, citations),
        section_completeness=_score_sections(
            resume,
            request.job_description,
            citations,
        ),
        keyword_match=_score_keywords(
            resume,
            request.job_description,
            citations,
        ),
        quantification=_score_quantification(resume, citations),
        readability=_score_readability(resume, citations),
    )
    overall = round(
        breakdown.format_compliance * 0.20
        + breakdown.section_completeness * 0.20
        + breakdown.keyword_match * 0.25
        + breakdown.quantification * 0.20
        + breakdown.readability * 0.15,
        2,
    )
    citations.append(
        Citation(
            rule_id="OVERALL_WEIGHTED_SCORE",
            source=FORMAT_RULES_SOURCE,
            note=(
                "Overall score uses weights: format 20%, sections 20%, "
                "keywords 25%, quantification 20%, readability 15%."
            ),
        )
    )
    return ATSScoreResult(
        overall=overall,
        breakdown=breakdown,
        citations=citations,
    )


def _score_format(resume: Resume, citations: list[Citation]) -> float:
    """Score deterministic ATS-safe signals available in the Resume model."""

    penalties = 0
    for flag in resume.red_flags:
        flag_text = flag.lower()
        if "insecure http" in flag_text:
            penalties += 30
        elif "long line" in flag_text:
            penalties += 20
        elif "section" in flag_text:
            penalties += 20
        else:
            penalties += 10

    score = float(max(0, 100 - penalties))
    citations.append(
        Citation(
            rule_id="FORMAT_COMPLIANCE",
            source=FORMAT_RULES_SOURCE,
            note=(
                "Started at 100 and deducted deterministic penalties "
                f"for {len(resume.red_flags)} detected red flag(s); "
                f"final score: {score:.2f}."
            ),
        )
    )
    return score


def _score_sections(
    resume: Resume,
    job_description,
    citations: list[Citation],
) -> float:
    """Score core sections while treating summary/projects as role-dependent."""

    is_student_role = _is_student_or_entry_role(job_description)
    required = {
        "contact": _has_contact(resume),
        "skills": bool(resume.skills),
        "experience": bool(resume.experience),
    }
    if is_student_role:
        required["education_or_projects"] = bool(
            resume.education or resume.projects
        )
    else:
        required["education_or_experience"] = bool(
            resume.education or resume.experience
        )

    optional = {
        "summary": bool(resume.summary),
        "projects": bool(resume.projects),
        "certifications": bool(resume.certifications),
    }
    required_score = sum(required.values()) / len(required) * 85
    optional_score = sum(optional.values()) / len(optional) * 15
    score = round(required_score + optional_score, 2)
    missing = [name for name, present in required.items() if not present]
    context = "student/entry-level" if is_student_role else "professional"
    citations.append(
        Citation(
            rule_id="ROLE_APPROPRIATE_SECTIONS",
            source=FORMAT_RULES_SOURCE,
            note=(
                f"Used {context} section expectations. "
                f"Required sections present: "
                f"{len(required) - len(missing)}/{len(required)}; "
                f"optional sections present: "
                f"{sum(optional.values())}/{len(optional)}."
                + (
                    f" Missing required: {', '.join(missing)}."
                    if missing
                    else ""
                )
            ),
        )
    )
    return score


def _score_keywords(
    resume: Resume,
    job_description,
    citations: list[Citation],
) -> float:
    """Match canonical skills with token boundaries and known aliases."""

    if job_description is None:
        score = 100.0 if resume.skills else 0.0
        citations.append(
            Citation(
                rule_id="KEYWORDS_NO_JOB_DESCRIPTION",
                source=FORMAT_RULES_SOURCE,
                note=(
                    "No job description supplied; keyword score is "
                    f"{score:.2f} based on whether a skills section exists."
                ),
            )
        )
        return score

    required = unique_canonical_skills(job_description.required_skills)
    preferred = unique_canonical_skills(job_description.preferred_skills)
    targets = required + [skill for skill in preferred if skill not in required]
    if not targets:
        citations.append(
            Citation(
                rule_id="KEYWORDS_NO_TARGET_SKILLS",
                source=FORMAT_RULES_SOURCE,
                note="No structured target skills were supplied.",
            )
        )
        return 100.0

    resume_text = normalize_text(resume_search_text(resume))
    matched = [
        skill
        for skill in targets
        if contains_skill(resume, resume_text, skill)
    ]
    required_matched = [skill for skill in required if skill in matched]
    preferred_matched = [skill for skill in preferred if skill in matched]
    required_score = (
        len(required_matched) / len(required) * 75 if required else 75
    )
    preferred_score = (
        len(preferred_matched) / len(preferred) * 25 if preferred else 25
    )
    score = round(required_score + preferred_score, 2)
    missing = [skill for skill in targets if skill not in matched]
    citations.append(
        Citation(
            rule_id="SEMANTIC_SKILL_MATCH",
            source=FORMAT_RULES_SOURCE,
            note=(
                f"Matched {len(required_matched)}/{len(required)} required "
                f"and {len(preferred_matched)}/{len(preferred)} preferred "
                "skills using canonical aliases and token boundaries."
            ),
        )
    )
    if missing:
        citations.append(
            Citation(
                rule_id="MISSING_TARGET_SKILLS",
                source=FORMAT_RULES_SOURCE,
                note=f"Unmatched target skills: {', '.join(missing)}.",
            )
        )
    return score


def _score_quantification(
    resume: Resume,
    citations: list[Citation],
) -> float:
    """Reward bullets combining a metric with action or business impact."""

    bullets = _all_bullets(resume)
    if not bullets:
        citations.append(
            Citation(
                rule_id="QUANTIFICATION_NO_BULLETS",
                source=FORMAT_RULES_SOURCE,
                note="No experience or project bullets were available.",
            )
        )
        return 0.0

    meaningful = [
        bullet
        for bullet in bullets
        if METRIC_PATTERN.search(bullet)
        and (
            _contains_any_word(bullet, ACTION_VERBS)
            or _contains_any_word(bullet, IMPACT_WORDS)
        )
    ]
    metric_only = [
        bullet
        for bullet in bullets
        if METRIC_PATTERN.search(bullet) and bullet not in meaningful
    ]
    score = round(
        (len(meaningful) / len(bullets) * 100)
        + (len(metric_only) / len(bullets) * 15),
        2,
    )
    score = min(score, 100.0)
    citations.append(
        Citation(
            rule_id="MEANINGFUL_QUANTIFICATION",
            source=FORMAT_RULES_SOURCE,
            note=(
                f"{len(meaningful)} of {len(bullets)} bullets combine a "
                f"measurable value with action/impact language; "
                f"{len(metric_only)} contain a metric without that context."
            ),
        )
    )
    return score


def _score_readability(
    resume: Resume,
    citations: list[Citation],
) -> float:
    """Score bullet length, sentence structure, verbs, and complexity."""

    bullets = _all_bullets(resume)
    if not bullets:
        citations.append(
            Citation(
                rule_id="READABILITY_NO_BULLETS",
                source=FORMAT_RULES_SOURCE,
                note="No experience or project bullets were available.",
            )
        )
        return 0.0

    scores = [_readability_score(bullet) for bullet in bullets]
    score = round(sum(scores) / len(scores), 2)
    citations.append(
        Citation(
            rule_id="PRACTICAL_READABILITY",
            source=FORMAT_RULES_SOURCE,
            note=(
                f"Average bullet readability was {score:.2f}, based on "
                "length, sentence structure, action verbs, and complexity."
            ),
        )
    )
    return score


def _readability_score(bullet: str) -> float:
    words = _words(bullet)
    word_count = len(words)
    sentence_count = max(1, len(SENTENCE_END_PATTERN.findall(bullet)))
    clauses = len(
        re.findall(r"\b(?:and|but|while|which|that)\b", bullet.lower())
    )
    score = 100.0
    if word_count < 5:
        score -= 35
    elif word_count > 35:
        score -= min(30, (word_count - 35) * 2)
    if sentence_count > 2:
        score -= 15
    if clauses > 2:
        score -= min(20, (clauses - 2) * 8)
    if not _contains_any_word(bullet, ACTION_VERBS):
        score -= 15
    if bullet[:1].islower():
        score -= 5
    return max(0.0, score)


def _is_student_or_entry_role(job_description) -> bool:
    if job_description is None:
        return False
    role_text = " ".join(
        value
        for value in [
            job_description.title,
            job_description.raw_text,
        ]
        if value
    ).lower()
    return any(
        term in role_text
        for term in (
            "intern",
            "internship",
            "student",
            "graduate",
            "entry level",
            "junior",
        )
    )


def _contains_any_word(text: str, words: set[str]) -> bool:
    return bool(set(_words(text)) & {word.strip() for word in words})


def _words(text: str) -> list[str]:
    return WORD_PATTERN.findall(normalize_text(text))


def _all_bullets(resume: Resume) -> list[str]:
    return [
        bullet
        for item in resume.experience
        for bullet in item.bullets
    ] + [
        bullet
        for project in resume.projects
        for bullet in project.bullets
    ]


def _has_contact(resume: Resume) -> bool:
    return bool(
        resume.contact.name
        or resume.contact.email
        or resume.contact.phone
        or resume.contact.linkedin
    )