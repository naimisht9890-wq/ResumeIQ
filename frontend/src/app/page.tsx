"use client";

import { ChangeEvent, DragEvent, FormEvent, useState } from "react";

type ScoreResult = {
  overall: number;
  breakdown: {
    format_compliance: number;
    section_completeness: number;
    keyword_match: number;
    quantification: number;
    readability: number;
  };
  citations: {
    rule_id: string;
    source: string;
    note: string;
  }[];
};

type SkillGapResult = {
  matched_required_skills: string[];
  missing_required_skills: string[];
  matched_preferred_skills: string[];
  missing_preferred_skills: string[];
  required_match_rate: number;
};

type ResumeData = {
  contact: {
    name?: string | null;
    email?: string | null;
    phone?: string | null;
    location?: string | null;
    linkedin?: string | null;
  };
  summary: string | null;
  experience: {
    title: string | null;
    company: string | null;
    start_date: string | null;
    end_date: string | null;
    bullets: string[];
  }[];
  education: {
    degree: string | null;
    school: string | null;
    start_date: string | null;
    end_date: string | null;
  }[];
  skills: string[];
  projects: {
    name: string | null;
    description: string | null;
    bullets: string[];
  }[];
  certifications: string[];
  red_flags: string[];
};
type JobData = Record<string, unknown>;
type FeedbackItem = {
  section: string;
  point: string;
  evidence: string | null;
  suggestion: string | null;
};
type CitationItem = {
  rule_id: string;
  source: string;
  note: string;
};
type FeedbackResult = {
  strengths: FeedbackItem[];
  weaknesses: FeedbackItem[];
  citations: CitationItem[];
};
type TailorResult = {
  changes: TailoredChange[];
  warnings: string[];
  citations: CitationItem[];
};
type TailoredChange = {
  section: string;
  original_text: string;
  suggested_text: string;
  reason: string;
  supported_by_resume: boolean;
};
type ChangeDecision = "pending" | "accepted" | "rejected";
type CoverLetterResult = {
  draft: string;
  resume_facts_used: string[];
  warnings: string[];
  citations: CitationItem[];
};
type JobStatusResult = {
  job_id: string;
  operation: string;
  status: "queued" | "running" | "completed" | "failed";
  error: string | null;
  result: unknown;
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export default function Home() {
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [jobDescription, setJobDescription] = useState("");
  const [score, setScore] = useState<ScoreResult | null>(null);
  const [skillGap, setSkillGap] = useState<SkillGapResult | null>(null);
  const [resumeData, setResumeData] = useState<ResumeData | null>(null);
  const [jobData, setJobData] = useState<JobData | null>(null);
  const [feedback, setFeedback] = useState<FeedbackResult | null>(null);
  const [tailoring, setTailoring] = useState<TailorResult | null>(null);
  const [changeDecisions, setChangeDecisions] = useState<
    Record<number, ChangeDecision>
  >({});
  const [coverLetter, setCoverLetter] = useState<CoverLetterResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [activeAction, setActiveAction] = useState("");
  const [error, setError] = useState("");

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setResumeFile(event.target.files?.[0] ?? null);
    setError("");
  }

  function handleFileDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setIsDragging(false);
    setResumeFile(event.dataTransfer.files[0] ?? null);
    setError("");
  }

  async function analyzeResume(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();

    if (!resumeFile || !jobDescription.trim()) {
      setError("Upload a resume and paste a job description first.");
      return;
    }

    setIsAnalyzing(true);
    setError("");
    setScore(null);
    setSkillGap(null);
    setResumeData(null);
    setJobData(null);
    setFeedback(null);
    setTailoring(null);
    setChangeDecisions({});
    setCoverLetter(null);

    try {
      const [resume, structuredJob] = await Promise.all([
        runJob<ResumeData>("resume_parsing", {
          filename: resumeFile.name,
          content_base64: await fileToBase64(resumeFile),
        }),
        runJob<JobData>("job_description_parsing", {
          text: jobDescription,
        }),
      ]);
      setResumeData(resume);
      setJobData(structuredJob);
      const analysisPayload = {
        resume,
        job_description: structuredJob,
      };
      const [scoreResult, skillGapResult] = await Promise.all([
        runJob<ScoreResult>("ats_scoring", analysisPayload),
        runJob<SkillGapResult>("skill_gap_analysis", analysisPayload),
      ]);

      setScore(scoreResult);
      setSkillGap(skillGapResult);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The analysis could not be completed.",
      );
    } finally {
      setIsAnalyzing(false);
    }
  }

  async function runJob<T>(operation: string, payload: unknown): Promise<T> {
    const jobResponse = await fetch(`${API_BASE_URL}/v1/jobs`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ operation, payload }),
    });

    if (!jobResponse.ok) {
      throw new Error(await getErrorMessage(jobResponse));
    }

    let job = (await jobResponse.json()) as JobStatusResult;
    while (job.status === "queued" || job.status === "running") {
      await new Promise((resolve) => window.setTimeout(resolve, 1000));
      const statusResponse = await fetch(
        `${API_BASE_URL}/v1/jobs/${encodeURIComponent(job.job_id)}`,
      );

      if (!statusResponse.ok) {
        throw new Error(await getErrorMessage(statusResponse));
      }

      job = (await statusResponse.json()) as JobStatusResult;
    }

    if (job.status === "failed") {
      throw new Error(job.error ?? `The ${operation} job failed.`);
    }
    if (job.result === null || typeof job.result !== "object") {
      throw new Error(`The ${operation} job completed without a result.`);
    }

    return job.result as T;
  }

  async function runOptionalAction(
    action: "feedback" | "tailoring" | "cover-letter",
  ) {
    if (!resumeData || !jobData) {
      setError("Analyze a resume and job description before continuing.");
      return;
    }

    setActiveAction(action);
    setError("");
    try {
      const payload = {
        resume: resumeData,
        job_description: jobData,
      };

      if (action === "feedback") {
        setFeedback(
          await runJob<FeedbackResult>("strengths_weaknesses", payload),
        );
      } else if (action === "tailoring") {
        const result = await runJob<TailorResult>("tailoring", payload);
        setTailoring(result);
        setChangeDecisions({});
      } else {
        setCoverLetter(
          await runJob<CoverLetterResult>("cover_letter", payload),
        );
      }
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The requested operation failed.",
      );
    } finally {
      setActiveAction("");
    }
  }

  async function downloadResume() {
    if (!resumeData) {
      setError("Analyze a resume before downloading it.");
      return;
    }

    setActiveAction("download");
    setError("");
    try {
      const acceptedChanges =
        tailoring?.changes.filter(
          (_, index) => changeDecisions[index] === "accepted",
        ) ?? [];
      const resumeForDownload = applyAcceptedChanges(
        resumeData,
        acceptedChanges,
      );
      const response = await fetch(`${API_BASE_URL}/v1/resumes/render`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resume: resumeForDownload }),
      });

      if (!response.ok) {
        throw new Error(await getErrorMessage(response));
      }

      const fileUrl = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = fileUrl;
      link.download = acceptedChanges.length
        ? "tailored_resume.docx"
        : "resume.docx";
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(fileUrl), 1000);
    } catch (requestError) {
      setError(
        requestError instanceof Error
          ? requestError.message
          : "The resume download failed.",
      );
    } finally {
      setActiveAction("");
    }
  }

  return (
    <main className="dashboard min-h-screen">
      <nav className="topbar">
        <div className="topbar-inner">
          <a className="brand" href="#top" aria-label="ResumeIQ home">
            <span className="brand-mark" aria-hidden="true">
              <svg viewBox="0 0 24 24" fill="none">
                <path
                  d="M7 3.75h7l4.25 4.3v12.2H7a2 2 0 0 1-2-2v-12.5a2 2 0 0 1 2-2Z"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinejoin="round"
                />
                <path
                  d="M14 4v4.5h4.25M8.5 12h7M8.5 15.5h5"
                  stroke="currentColor"
                  strokeWidth="1.6"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </span>
            <span>Resume<span className="brand-accent">IQ</span></span>
          </a>
          <div className="topbar-links">
            <a href="#analysis">Workspace</a>
            <a href="#insights">Insights</a>
          </div>
          <span className="topbar-status">
            <span className="status-dot" />
            AI resume intelligence
          </span>
        </div>
      </nav>

      <div id="top" className="page-content">
        <section className="hero">
          <div className="hero-copy">
            <p className="eyebrow">
              <span className="eyebrow-sparkle">✳</span>
              Your next role starts here
            </p>
            <h1 className="hero-title">
              Make your resume
              <br />
              <span>work smarter.</span>
            </h1>
            <p className="hero-description">
              Get a clearer picture of how your experience aligns with the
              role. Practical, explainable insights to help you apply with
              confidence.
            </p>
            <div className="hero-points">
              <span><i className="point-check">✓</i> Transparent ATS scoring</span>
              <span><i className="point-check">✓</i> Resume-grounded guidance</span>
            </div>
          </div>
          <div className="hero-note">
            <span className="hero-note-icon" aria-hidden="true">✦</span>
            <div>
              <strong>Built for better applications</strong>
              <p>One workspace for your resume and the role you want.</p>
            </div>
          </div>
        </section>

        <div className="workspace-grid">
          <section id="analysis" className="workspace-panel">
            <div className="section-heading">
              <span className="section-index">01</span>
              <div>
                <p className="section-kicker">Start with the essentials</p>
                <h2>Set up your analysis</h2>
              </div>
            </div>

          <form
            onSubmit={analyzeResume}
            className="glass-card upload-form"
          >
            <label className="field-label">
              <span className="field-heading">
                <span className="field-number">1</span>
                Upload your resume
              </span>
              <span
                className={`upload-dropzone${isDragging ? " is-dragging" : ""}${resumeFile ? " has-file" : ""}`}
                onDragOver={(event) => {
                  event.preventDefault();
                  setIsDragging(true);
                }}
                onDragLeave={(event) => {
                  if (!event.currentTarget.contains(event.relatedTarget as Node | null)) {
                    setIsDragging(false);
                  }
                }}
                onDrop={handleFileDrop}
              >
                <span className="upload-icon" aria-hidden="true">
                  <svg viewBox="0 0 24 24" fill="none">
                    <path
                      d="M12 16V4m0 0L7.5 8.5M12 4l4.5 4.5M5 15.5v3A1.5 1.5 0 0 0 6.5 20h11a1.5 1.5 0 0 0 1.5-1.5v-3"
                      stroke="currentColor"
                      strokeWidth="1.7"
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    />
                  </svg>
                </span>
                <span>
                  <strong>{resumeFile ? resumeFile.name : "Drop your resume here"}</strong>
                  <small>{resumeFile ? "Ready to analyze" : "or click to browse · PDF, DOCX, or TXT"}</small>
                </span>
                <input
                  type="file"
                  accept=".pdf,.docx,.txt"
                  onChange={handleFileChange}
                  className="sr-only"
                />
              </span>
            </label>

            <label className="field-label">
              <span className="field-heading">
                <span className="field-number">2</span>
                Add the target job description
              </span>
              <textarea
                value={jobDescription}
                onChange={(event) => setJobDescription(event.target.value)}
                placeholder="Paste the job description to compare its requirements with your experience..."
                rows={7}
                className="job-description-input"
              />
              <span className="field-hint">
                Include the full description for the most relevant skill-match insights.
              </span>
            </label>

            {error && (
              <p role="alert" className="error-message">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={isAnalyzing || !resumeFile || !jobDescription.trim()}
              className="primary-button"
            >
              {isAnalyzing ? (
                <>
                  <span className="loading-spinner" aria-hidden="true" />
                  Analyzing your resume
                </>
              ) : (
                <>
                  Analyze my resume
                  <span aria-hidden="true">→</span>
                </>
              )}
            </button>
            <p className="privacy-note">
              Resume text is processed for your analysis and AI-generated suggestions.
            </p>
          </form>
        </section>

        <section id="insights" className="insights-column">
          <div className="section-heading insights-heading">
            <span className="section-index">02</span>
            <div>
              <p className="section-kicker">A clearer view of your fit</p>
              <h2>Your resume insights</h2>
            </div>
          </div>

          <div className="glass-card score-card">
            <div className="score-card-heading">
              <div>
                <p className="card-eyebrow">Resume overview</p>
                <h3>ATS compatibility</h3>
              </div>
              {score && <span className="complete-badge"><span /> Analysis complete</span>}
            </div>
            <div className="score-overview">
              <div
                className="score-gauge"
                style={{
                  background: `conic-gradient(#65e0c0 ${score ? score.overall : 0}%, #253448 0)`,
                }}
              >
                <div className="score-gauge-inner">
                  <strong>{score ? Math.round(score.overall) : "--"}</strong>
                  <span>out of 100</span>
                </div>
              </div>
              <div className="score-summary">
                <p className="score-label">
                  {score ? "Your current score" : "Your score will appear here"}
                </p>
                <p>
                  {score
                    ? "A snapshot of how well your resume aligns with common ATS checks and this role."
                    : "Upload your resume and add a job description to see your compatibility breakdown."}
                </p>
              </div>
            </div>
            {score && (
              <div className="score-breakdown">
                {Object.entries(score.breakdown).map(([label, value]) => (
                  <div key={label} className="score-metric">
                    <p>{label.replaceAll("_", " ")}</p>
                    <div className="metric-track">
                      <span
                        style={{
                          width: `${Math.max(0, Math.min(100, value))}%`,
                        }}
                      />
                    </div>
                    <strong>{Math.round(value)}<small>/100</small></strong>
                  </div>
                ))}
              </div>
            )}
            {score && (
              <details className="score-citations">
                <summary>How this score is calculated</summary>
                <div>
                  {score.citations.map((citation) => (
                    <p key={citation.rule_id}>
                      <strong>{citation.rule_id.replaceAll("_", " ")}</strong>
                      <span>{citation.note}</span>
                    </p>
                  ))}
                </div>
              </details>
            )}
          </div>

          <div className="glass-card skill-card">
            <div className="skill-card-heading">
              <div>
                <p className="card-eyebrow">Role alignment</p>
                <h3>Skill gap analysis</h3>
              </div>
              <div className="match-rate">
                <strong>{skillGap ? `${Math.round(skillGap.required_match_rate)}%` : "--"}</strong>
                <span>required match</span>
              </div>
            </div>
            {skillGap && (
              <div className="skill-progress">
                <span
                  style={{
                    width: `${Math.max(0, Math.min(100, skillGap.required_match_rate))}%`,
                  }}
                />
              </div>
            )}

            {skillGap && (
              <div className="skill-lists">
                <SkillList
                  title="Skills found in your resume"
                  skills={skillGap.matched_required_skills}
                  color="emerald"
                />
                <SkillList
                  title="Required skills to address"
                  skills={skillGap.missing_required_skills}
                  color="rose"
                />
                <SkillList
                  title="Preferred skills to address"
                  skills={skillGap.missing_preferred_skills}
                  color="amber"
                />
              </div>
            )}
            {!skillGap && (
              <p className="insight-placeholder">
                Add a target role to see matched and missing skills side by side.
              </p>
            )}
          </div>

          {score && skillGap && (
            <div className="glass-card actions-card">
              <div>
                <p className="card-eyebrow">Keep improving</p>
                <h3>Go beyond the score</h3>
                <p className="actions-description">
                  Choose an insight to generate from your resume and this job description.
                </p>
              </div>
              <div className="action-grid">
                <ActionButton
                  onClick={() => runOptionalAction("feedback")}
                  disabled={Boolean(activeAction)}
                  busy={activeAction === "feedback"}
                >
                  Strengths &amp; weaknesses
                </ActionButton>
                <ActionButton
                  onClick={() => runOptionalAction("tailoring")}
                  disabled={Boolean(activeAction)}
                  busy={activeAction === "tailoring"}
                >
                  Review tailoring suggestions
                </ActionButton>
                <ActionButton
                  onClick={() => runOptionalAction("cover-letter")}
                  disabled={Boolean(activeAction)}
                  busy={activeAction === "cover-letter"}
                >
                  Generate cover letter
                </ActionButton>
                <ActionButton
                  onClick={downloadResume}
                  disabled={Boolean(activeAction)}
                  busy={activeAction === "download"}
                >
                  {acceptedChangeCount(tailoring, changeDecisions) > 0
                    ? `Download tailored DOCX (${acceptedChangeCount(tailoring, changeDecisions)} accepted)`
                    : "Download resume DOCX"}
                </ActionButton>
              </div>
            </div>
          )}

          {feedback && (
            <FeedbackPanel
              title="Strengths"
              items={feedback.strengths}
              citations={feedback.citations}
            />
          )}
          {feedback && (
            <FeedbackPanel
              title="Areas to improve"
              items={feedback.weaknesses}
            />
          )}

          {tailoring && (
            <div className="glass-card result-card">
              <div className="result-card-heading">
                <div>
                  <p className="card-eyebrow">Resume tailoring</p>
                  <h3>Review suggested changes</h3>
                </div>
                <span className="result-icon">↗</span>
              </div>
              {tailoring.warnings.map((warning) => (
                <p key={warning} className="warning-message">
                  {warning}
                </p>
              ))}
              <div className="suggestion-list">
                {tailoring.changes.map((change, index) => (
                  <article
                    key={`${change.section}-${index}`}
                    className="suggestion-item"
                  >
                    <p className="suggestion-section">
                      {change.section}
                      <span className={change.supported_by_resume ? "fact-supported" : "fact-review"}>
                        {change.supported_by_resume ? "Grounded in your resume" : "Review carefully"}
                      </span>
                    </p>
                    <p className="suggestion-original">
                      <span>Current</span>{change.original_text}
                    </p>
                    <p className="suggestion-proposed">
                      <span>Suggested</span>{change.suggested_text}
                    </p>
                    <p className="suggestion-reason">
                      {change.reason}
                    </p>
                    <div className="decision-row">
                      <button
                        type="button"
                        onClick={() =>
                          setChangeDecisions((current) => ({
                            ...current,
                            [index]: "accepted",
                          }))
                        }
                        aria-pressed={changeDecisions[index] === "accepted"}
                        className={`decision-button accept-button${changeDecisions[index] === "accepted" ? " is-selected" : ""}`}
                      >
                        Accept
                      </button>
                      <button
                        type="button"
                        onClick={() =>
                          setChangeDecisions((current) => ({
                            ...current,
                            [index]: "rejected",
                          }))
                        }
                        aria-pressed={changeDecisions[index] === "rejected"}
                        className={`decision-button reject-button${changeDecisions[index] === "rejected" ? " is-selected" : ""}`}
                      >
                        Reject
                      </button>
                      <span className="decision-status">
                        {changeDecisions[index] ?? "Pending"}
                      </span>
                    </div>
                  </article>
                ))}
                {tailoring.changes.length === 0 && (
                  <p className="insight-placeholder">
                    No text changes were suggested. Check the notes above for more context.
                  </p>
                )}
              </div>
              <CitationsPanel citations={tailoring.citations} />
              {acceptedChangeCount(tailoring, changeDecisions) > 0 && (
                <p className="accepted-message">
                  {acceptedChangeCount(tailoring, changeDecisions)} accepted
                  change(s) will be included in the tailored DOCX. Pending and
                  rejected suggestions will be left out.
                </p>
              )}
            </div>
          )}

          {coverLetter && (
            <div className="glass-card result-card">
              <div className="result-card-heading">
                <div>
                  <p className="card-eyebrow">Personalized draft</p>
                  <h3>Cover letter</h3>
                </div>
                <span className="result-icon">✎</span>
              </div>
              {coverLetter.warnings.map((warning) => (
                <p key={warning} className="warning-message">
                  {warning}
                </p>
              ))}
              <p className="cover-letter-draft">
                {coverLetter.draft}
              </p>
              <div className="facts-used">
                <p>Resume facts referenced</p>
                <div>
                  {coverLetter.resume_facts_used.map((fact) => (
                    <span key={fact}>
                      {fact}
                    </span>
                  ))}
                </div>
              </div>
              <CitationsPanel citations={coverLetter.citations} />
            </div>
          )}

          {!score && !skillGap && (
            <div className="empty-state">
              <div className="empty-orbit" aria-hidden="true"><span>✦</span></div>
              <p className="card-eyebrow">Your next step, made clearer</p>
              <h3>Your insights will appear here</h3>
              <p>
                Start with your resume and a job description. ResumeIQ will map
                the match, surface opportunities, and keep its recommendations
                grounded in your experience.
              </p>
            </div>
          )}
        </section>
      </div>
      </div>
      <footer className="page-footer">
        <span>ResumeIQ</span>
        <span>Thoughtful tools for your next career move.</span>
      </footer>
    </main>
  );
}

async function fileToBase64(file: File): Promise<string> {
  const bytes = new Uint8Array(await file.arrayBuffer());
  let binary = "";
  const chunkSize = 0x8000;

  for (let offset = 0; offset < bytes.length; offset += chunkSize) {
    binary += String.fromCharCode(
      ...bytes.subarray(offset, offset + chunkSize),
    );
  }

  return btoa(binary);
}

function ActionButton({
  children,
  onClick,
  disabled,
  busy,
}: {
  children: React.ReactNode;
  onClick: () => void;
  disabled: boolean;
  busy: boolean;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className="action-button"
    >
      {busy ? (
        <>
          <span className="loading-spinner" aria-hidden="true" />
          Working...
        </>
      ) : (
        <>
          {children}
          <span className="action-arrow" aria-hidden="true">→</span>
        </>
      )}
    </button>
  );
}

function acceptedChangeCount(
  result: TailorResult | null,
  decisions: Record<number, ChangeDecision>,
): number {
  return (
    result?.changes.filter(
      (_, index) => decisions[index] === "accepted",
    ).length ?? 0
  );
}

function applyAcceptedChanges(
  source: ResumeData,
  changes: TailoredChange[],
): ResumeData {
  const updated: ResumeData = structuredClone(source);

  for (const change of changes) {
    let applied = false;

    if (change.section.toLowerCase() === "summary") {
      if (updated.summary === change.original_text) {
        updated.summary = change.suggested_text;
        applied = true;
      }
    } else if (change.section.toLowerCase() === "experience") {
      for (const item of updated.experience) {
        const bulletIndex = item.bullets.indexOf(change.original_text);
        if (bulletIndex !== -1) {
          item.bullets[bulletIndex] = change.suggested_text;
          applied = true;
          break;
        }
      }
    } else if (
      ["project", "projects"].includes(change.section.toLowerCase())
    ) {
      for (const project of updated.projects) {
        if (project.description === change.original_text) {
          project.description = change.suggested_text;
          applied = true;
          break;
        }

        if (project.name === change.original_text) {
          project.name = change.suggested_text;
          applied = true;
          break;
        }

        const bulletIndex = project.bullets.indexOf(change.original_text);
        if (bulletIndex !== -1) {
          project.bullets[bulletIndex] = change.suggested_text;
          applied = true;
          break;
        }
      }
    }

    if (!applied) {
      throw new Error(
        `Could not apply accepted ${change.section} change: the original text no longer matches the resume.`,
      );
    }
  }

  return updated;
}

function FeedbackPanel({
  title,
  items,
  citations,
}: {
  title: string;
  items: FeedbackItem[];
  citations?: CitationItem[];
}) {
  return (
    <div className="glass-card feedback-card">
      <div className="result-card-heading">
        <div>
          <p className="card-eyebrow">Personalized feedback</p>
          <h3>{title}</h3>
        </div>
      </div>
      <div className="feedback-list">
        {items.map((item, index) => (
          <article
            key={`${item.section}-${index}`}
            className="feedback-item"
          >
            <p className="feedback-section">
              {item.section}
            </p>
            <p className="feedback-point">{item.point}</p>
            {item.evidence && (
              <p className="feedback-detail">
                <strong>Evidence</strong>{item.evidence}
              </p>
            )}
            {item.suggestion && (
              <p className="feedback-detail">
                <strong>Suggestion</strong>
                {item.suggestion}
              </p>
            )}
          </article>
        ))}
        {items.length === 0 && (
          <p className="insight-placeholder">No findings returned.</p>
        )}
      </div>
      {citations && <CitationsPanel citations={citations} />}
    </div>
  );
}

function CitationsPanel({ citations }: { citations: CitationItem[] }) {
  if (citations.length === 0) {
    return null;
  }

  return (
    <details className="score-citations">
      <summary>Grounded in {citations.length} knowledge source(s)</summary>
      <div>
        {citations.map((citation) => (
          <p key={citation.rule_id}>
            <strong>{citation.rule_id.replaceAll("_", " ")}</strong>
            <span>{citation.note}</span>
          </p>
        ))}
      </div>
    </details>
  );
}

function SkillList({
  title,
  skills,
  color,
}: {
  title: string;
  skills: string[];
  color: "emerald" | "rose" | "amber";
}) {
  const styles = {
    emerald: "skill-positive",
    rose: "skill-negative",
    amber: "skill-neutral",
  };

  return (
    <div>
      <p className="skill-list-title">{title}</p>
      {skills.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {skills.map((skill) => (
            <span
              key={skill}
              className={`skill-pill ${styles[color]}`}
            >
              {skill}
            </span>
          ))}
        </div>
      ) : (
        <p className="insight-placeholder">None detected</p>
      )}
    </div>
  );
}

async function getErrorMessage(response: Response): Promise<string> {
  try {
    const data = await response.json();
    return data.detail ?? "The API request failed.";
  } catch {
    return "The API request failed.";
  }
}
