from pydantic import BaseModel, Field


class ContactInfo(BaseModel):
    name: str | None = None
    email: str | None = None
    phone: str | None = None
    location: str | None = None
    linkedin: str | None = None


class ExperienceItem(BaseModel):
    title: str | None = None
    company: str | None = None
    start_date: str | None = None
    end_date: str | None = None
    bullets: list[str] = Field(default_factory=list)


class EducationItem(BaseModel):
    degree: str | None = None
    school: str | None = None
    start_date: str | None = None
    end_date: str | None = None


class ProjectItem(BaseModel):
    name: str | None = None
    description: str | None = None
    bullets: list[str] = Field(default_factory=list)


class Resume(BaseModel):
    contact: ContactInfo = Field(default_factory=ContactInfo)
    summary: str | None = None
    experience: list[ExperienceItem] = Field(default_factory=list)
    education: list[EducationItem] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    projects: list[ProjectItem] = Field(default_factory=list)
    certifications: list[str] = Field(default_factory=list)
    red_flags: list[str] = Field(default_factory=list)


class JobDescription(BaseModel):
    title: str | None = None
    company: str | None = None
    raw_text: str
    required_skills: list[str] = Field(default_factory=list)
    preferred_skills: list[str] = Field(default_factory=list)
    responsibilities: list[str] = Field(default_factory=list)

class JobDescriptionRequest(BaseModel):
    text: str

class ATSScoreRequest(BaseModel):
    resume: Resume
    job_description: JobDescription | None = None

class SkillGapAnalysisRequest(BaseModel):
    resume: Resume
    job_description: JobDescription


class TailorResumeRequest(BaseModel):
    resume: Resume
    job_description: JobDescription



class ScoreBreakdown(BaseModel):
    format_compliance: float
    section_completeness: float
    keyword_match: float
    quantification: float
    readability: float


class Citation(BaseModel):
    rule_id: str
    source: str
    note: str

class SkillGapAnalysisResult(BaseModel):
    matched_required_skills: list[str] = Field(default_factory=list)
    missing_required_skills: list[str] = Field(default_factory=list)
    matched_preferred_skills: list[str] = Field(default_factory=list)
    missing_preferred_skills: list[str] = Field(default_factory=list)
    required_match_rate: float
    total_target_skills: int
    matched_target_skills: int
    citations: list[Citation] = Field(default_factory=list)


class TailoredChange(BaseModel):
    section: str
    original_text: str
    suggested_text: str
    reason: str
    supported_by_resume: bool


class TailorResumeResult(BaseModel):
    changes: list[TailoredChange] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)

    
class ATSScoreResult(BaseModel):
    overall: float
    breakdown: ScoreBreakdown
    citations: list[Citation] = Field(default_factory=list)


class FeedbackItem(BaseModel):
    section: str
    point: str
    evidence: str | None = None
    suggestion: str | None = None


class StrengthsWeaknessesRequest(BaseModel):
    resume: Resume
    job_description: JobDescription | None = None

    
class StrengthsWeaknessesResult(BaseModel):
    strengths: list[FeedbackItem]
    weaknesses: list[FeedbackItem]