from app.models.schemas import (
    Citation,
    SkillGapAnalysisRequest,
    SkillGapAnalysisResult,
)
from app.services.ats_scoring import (
    _canonical_skill,
    _contains_skill,
    _normalize_text,
    _resume_search_text,
)


def analyze_skill_gap(
    request: SkillGapAnalysisRequest,
) -> SkillGapAnalysisResult:
    """
    Compare resume skills and evidence with job-description skills.
    """

    resume = request.resume
    job_description = request.job_description

    required = _unique_canonical_skills(
        job_description.required_skills
    )
    preferred = _unique_canonical_skills(
        job_description.preferred_skills
    )

    resume_text = _normalize_text(
        _resume_search_text(resume)
    )

    matched_required = [
        skill
        for skill in required
        if _contains_skill(
            resume=resume,
            resume_text=resume_text,
            target=skill,
        )
    ]

    missing_required = [
        skill
        for skill in required
        if skill not in matched_required
    ]

    matched_preferred = [
        skill
        for skill in preferred
        if _contains_skill(
            resume=resume,
            resume_text=resume_text,
            target=skill,
        )
    ]

    missing_preferred = [
        skill
        for skill in preferred
        if skill not in matched_preferred
    ]

    all_targets = _unique_items(
        required + preferred
    )
    all_matched = _unique_items(
        matched_required + matched_preferred
    )

    required_match_rate = (
        round(
            len(matched_required) / len(required) * 100,
            2,
        )
        if required
        else 100.0
    )

    citations = [
        Citation(
            rule_id="SKILL_GAP_CANONICAL_MATCH",
            source="deterministic_skill_rules",
            note=(
                "Skills were normalized with aliases and matched "
                "using token boundaries."
            ),
        ),
        Citation(
            rule_id="SKILL_GAP_REQUIRED_RATE",
            source="deterministic_skill_rules",
            note=(
                f"Matched {len(matched_required)} of "
                f"{len(required)} required skills."
            ),
        ),
    ]

    if missing_required:
        citations.append(
            Citation(
                rule_id="MISSING_REQUIRED_SKILLS",
                source="deterministic_skill_rules",
                note=(
                    "Missing required skills: "
                    f"{', '.join(missing_required)}."
                ),
            )
        )

    return SkillGapAnalysisResult(
        matched_required_skills=matched_required,
        missing_required_skills=missing_required,
        matched_preferred_skills=matched_preferred,
        missing_preferred_skills=missing_preferred,
        required_match_rate=required_match_rate,
        total_target_skills=len(all_targets),
        matched_target_skills=len(all_matched),
        citations=citations,
    )


def _unique_canonical_skills(
    skills: list[str],
) -> list[str]:
    result: list[str] = []

    for skill in skills:
        canonical = _canonical_skill(skill)

        if canonical and canonical not in result:
            result.append(canonical)

    return result


def _unique_items(items: list[str]) -> list[str]:
    result: list[str] = []

    for item in items:
        if item not in result:
            result.append(item)

    return result