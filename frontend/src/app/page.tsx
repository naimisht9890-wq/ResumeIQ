"use client";

import { ChangeEvent, FormEvent, useState } from "react";

type ScoreResult = {
  overall: number;
  breakdown: {
    format_compliance: number;
    section_completeness: number;
    keyword_match: number;
    quantification: number;
    readability: number;
  };
};

type SkillGapResult = {
  matched_required_skills: string[];
  missing_required_skills: string[];
  matched_preferred_skills: string[];
  missing_preferred_skills: string[];
  required_match_rate: number;
};

type ResumeData = Record<string, unknown>;
type JobData = Record<string, unknown>;
type FeedbackItem = {
  section: string;
  point: string;
  evidence: string | null;
  suggestion: string | null;
};
type FeedbackResult = {
  strengths: FeedbackItem[];
  weaknesses: FeedbackItem[];
};
type TailorResult = {
  changes: {
    section: string;
    original_text: string;
    suggested_text: string;
    reason: string;
    supported_by_resume: boolean;
  }[];
  warnings: string[];
};
type CoverLetterResult = {
  draft: string;
  resume_facts_used: string[];
  warnings: string[];
};

const API_BASE_URL =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://127.0.0.1:8000";

export default function Home() {
  const [resumeFile, setResumeFile] = useState<File | null>(null);
  const [jobDescription, setJobDescription] = useState("");
  const [score, setScore] = useState<ScoreResult | null>(null);
  const [skillGap, setSkillGap] = useState<SkillGapResult | null>(null);
  const [resumeData, setResumeData] = useState<ResumeData | null>(null);
  const [jobData, setJobData] = useState<JobData | null>(null);
  const [feedback, setFeedback] = useState<FeedbackResult | null>(null);
  const [tailoring, setTailoring] = useState<TailorResult | null>(null);
  const [coverLetter, setCoverLetter] = useState<CoverLetterResult | null>(null);
  const [isAnalyzing, setIsAnalyzing] = useState(false);
  const [activeAction, setActiveAction] = useState("");
  const [error, setError] = useState("");

  function handleFileChange(event: ChangeEvent<HTMLInputElement>) {
    setResumeFile(event.target.files?.[0] ?? null);
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
    setCoverLetter(null);

    try {
      const resumeForm = new FormData();
      resumeForm.append("file", resumeFile);

      const resumeResponse = await fetch(
        `${API_BASE_URL}/v1/resumes`,
        {
          method: "POST",
          body: resumeForm,
        },
      );

      if (!resumeResponse.ok) {
        throw new Error(await getErrorMessage(resumeResponse));
      }

      const resume = await resumeResponse.json();
      setResumeData(resume);
      const jobResponse = await fetch(
        `${API_BASE_URL}/v1/job-descriptions`,
        {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: jobDescription }),
        },
      );

      if (!jobResponse.ok) {
        throw new Error(await getErrorMessage(jobResponse));
      }

      const structuredJob = await jobResponse.json();
      setJobData(structuredJob);
      const [scoreResponse, gapResponse] = await Promise.all([
        fetch(`${API_BASE_URL}/v1/ats-score`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            resume,
            job_description: structuredJob,
          }),
        }),
        fetch(`${API_BASE_URL}/v1/analysis/skill-gap`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({
            resume,
            job_description: structuredJob,
          }),
        }),
      ]);

      if (!scoreResponse.ok) {
        throw new Error(await getErrorMessage(scoreResponse));
      }
      if (!gapResponse.ok) {
        throw new Error(await getErrorMessage(gapResponse));
      }

      setScore(await scoreResponse.json());
      setSkillGap(await gapResponse.json());
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

  async function requestJson<T>(path: string, body: unknown): Promise<T> {
    const response = await fetch(`${API_BASE_URL}${path}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });

    if (!response.ok) {
      throw new Error(await getErrorMessage(response));
    }

    return response.json() as Promise<T>;
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
          await requestJson<FeedbackResult>(
            "/v1/analysis/strengths-weaknesses",
            payload,
          ),
        );
      } else if (action === "tailoring") {
        setTailoring(
          await requestJson<TailorResult>(
            "/v1/resumes/tailor",
            payload,
          ),
        );
      } else {
        setCoverLetter(
          await requestJson<CoverLetterResult>(
            "/v1/cover-letters",
            payload,
          ),
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
      const response = await fetch(`${API_BASE_URL}/v1/resumes/render`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ resume: resumeData }),
      });

      if (!response.ok) {
        throw new Error(await getErrorMessage(response));
      }

      const fileUrl = URL.createObjectURL(await response.blob());
      const link = document.createElement("a");
      link.href = fileUrl;
      link.download = "resume.docx";
      link.click();
      URL.revokeObjectURL(fileUrl);
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
    <main className="min-h-screen bg-[#f5f7fb] text-slate-950">
      <nav className="border-b border-slate-200 bg-white">
        <div className="mx-auto flex max-w-6xl items-center justify-between px-5 py-4">
          <div className="flex items-center gap-3">
            <div className="grid size-9 place-items-center rounded-xl bg-indigo-600 font-bold text-white">
              R
            </div>
            <span className="text-lg font-semibold tracking-tight">
              ResumeIQ
            </span>
          </div>
          <span className="hidden rounded-full bg-indigo-50 px-3 py-1 text-xs font-medium text-indigo-700 sm:block">
            AI-powered resume intelligence
          </span>
        </div>
      </nav>

      <div className="mx-auto grid max-w-6xl gap-8 px-5 py-10 lg:grid-cols-[0.9fr_1.1fr]">
        <section>
          <p className="mb-3 text-sm font-semibold uppercase tracking-[0.2em] text-indigo-600">
            Resume analysis workspace
          </p>
          <h1 className="max-w-xl text-4xl font-semibold tracking-tight sm:text-5xl">
            Turn your resume into a stronger application.
          </h1>
          <p className="mt-5 max-w-xl text-lg leading-8 text-slate-600">
            Upload your resume and add a target job description to receive a
            transparent ATS score, skill gaps, and evidence-based insights.
          </p>

          <form
            onSubmit={analyzeResume}
            className="mt-8 space-y-5 rounded-3xl border border-slate-200 bg-white p-5 shadow-sm sm:p-7"
          >
            <label className="block">
              <span className="mb-2 block text-sm font-semibold">
                Resume file
              </span>
              <span className="flex cursor-pointer items-center justify-between rounded-2xl border border-dashed border-indigo-300 bg-indigo-50/50 px-4 py-4 text-sm text-slate-600 transition hover:border-indigo-500 hover:bg-indigo-50">
                <span>
                  {resumeFile ? resumeFile.name : "Choose PDF, DOCX, or TXT"}
                </span>
                <span className="rounded-lg bg-white px-3 py-2 font-medium text-indigo-700 shadow-sm">
                  Browse
                </span>
                <input
                  type="file"
                  accept=".pdf,.docx,.txt"
                  onChange={handleFileChange}
                  className="sr-only"
                />
              </span>
            </label>

            <label className="block">
              <span className="mb-2 block text-sm font-semibold">
                Target job description
              </span>
              <textarea
                value={jobDescription}
                onChange={(event) => setJobDescription(event.target.value)}
                placeholder="Paste the job description here..."
                rows={9}
                className="w-full resize-none rounded-2xl border border-slate-200 bg-slate-50 px-4 py-3 text-sm outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:bg-white focus:ring-4 focus:ring-indigo-100"
              />
            </label>

            {error && (
              <p className="rounded-xl bg-rose-50 px-4 py-3 text-sm text-rose-700">
                {error}
              </p>
            )}

            <button
              type="submit"
              disabled={isAnalyzing}
              className="w-full rounded-2xl bg-indigo-600 px-5 py-3.5 text-sm font-semibold text-white transition hover:bg-indigo-700 disabled:cursor-not-allowed disabled:opacity-60"
            >
              {isAnalyzing ? "Analyzing your resume..." : "Analyze resume"}
            </button>
          </form>
        </section>

        <section className="space-y-5">
          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex items-center justify-between">
              <div>
                <p className="text-sm font-medium text-slate-500">
                  Overall ATS score
                </p>
                <p className="mt-1 text-3xl font-semibold">
                  {score ? `${score.overall}/100` : "--"}
                </p>
              </div>
              <div className="grid size-16 place-items-center rounded-full bg-indigo-50 text-xl font-semibold text-indigo-700">
                {score ? Math.round(score.overall) : "--"}
              </div>
            </div>
            {score && (
              <div className="mt-6 grid grid-cols-2 gap-3 sm:grid-cols-3">
                {Object.entries(score.breakdown).map(([label, value]) => (
                  <div key={label} className="rounded-2xl bg-slate-50 p-3">
                    <p className="text-xs capitalize text-slate-500">
                      {label.replaceAll("_", " ")}
                    </p>
                    <p className="mt-1 font-semibold">{value}</p>
                  </div>
                ))}
              </div>
            )}
          </div>

          <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
            <p className="text-sm font-medium text-slate-500">
              Job skill alignment
            </p>
            <p className="mt-1 text-3xl font-semibold">
              {skillGap ? `${skillGap.required_match_rate}%` : "--"}
            </p>
            <p className="mt-1 text-sm text-slate-500">
              Required skills matched
            </p>

            {skillGap && (
              <div className="mt-6 space-y-5">
                <SkillList
                  title="Matched skills"
                  skills={skillGap.matched_required_skills}
                  color="emerald"
                />
                <SkillList
                  title="Missing required skills"
                  skills={skillGap.missing_required_skills}
                  color="rose"
                />
                <SkillList
                  title="Missing preferred skills"
                  skills={skillGap.missing_preferred_skills}
                  color="amber"
                />
              </div>
            )}
          </div>

          {score && skillGap && (
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <p className="font-semibold">Next steps</p>
              <p className="mt-1 text-sm text-slate-500">
                Generate each AI result only when you choose it.
              </p>
              <div className="mt-4 grid gap-3 sm:grid-cols-2">
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
                  Download resume DOCX
                </ActionButton>
              </div>
            </div>
          )}

          {feedback && (
            <FeedbackPanel title="Strengths" items={feedback.strengths} />
          )}
          {feedback && (
            <FeedbackPanel title="Areas to improve" items={feedback.weaknesses} />
          )}

          {tailoring && (
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="font-semibold">Review suggested changes</h2>
              {tailoring.warnings.map((warning) => (
                <p
                  key={warning}
                  className="mt-3 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800"
                >
                  {warning}
                </p>
              ))}
              <div className="mt-4 space-y-4">
                {tailoring.changes.map((change, index) => (
                  <article
                    key={`${change.section}-${index}`}
                    className="rounded-2xl border border-slate-200 p-4"
                  >
                    <p className="text-xs font-semibold uppercase text-indigo-700">
                      {change.section}
                      {change.supported_by_resume
                        ? " · Supported by resume"
                        : " · Review carefully"}
                    </p>
                    <p className="mt-3 text-sm text-slate-500">
                      Original: {change.original_text}
                    </p>
                    <p className="mt-2 text-sm font-medium">
                      Suggested: {change.suggested_text}
                    </p>
                    <p className="mt-2 text-xs text-slate-500">
                      {change.reason}
                    </p>
                  </article>
                ))}
                {tailoring.changes.length === 0 && (
                  <p className="text-sm text-slate-500">
                    No text changes were suggested. Check the warnings above.
                  </p>
                )}
              </div>
            </div>
          )}

          {coverLetter && (
            <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
              <h2 className="font-semibold">Cover letter draft</h2>
              {coverLetter.warnings.map((warning) => (
                <p
                  key={warning}
                  className="mt-3 rounded-xl bg-amber-50 px-4 py-3 text-sm text-amber-800"
                >
                  {warning}
                </p>
              ))}
              <p className="mt-4 whitespace-pre-wrap text-sm leading-7 text-slate-700">
                {coverLetter.draft}
              </p>
              <div className="mt-4 border-t border-slate-100 pt-4">
                <p className="text-xs font-semibold text-slate-500">
                  Resume facts referenced
                </p>
                <div className="mt-2 flex flex-wrap gap-2">
                  {coverLetter.resume_facts_used.map((fact) => (
                    <span
                      key={fact}
                      className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600"
                    >
                      {fact}
                    </span>
                  ))}
                </div>
              </div>
            </div>
          )}

          {!score && !skillGap && (
            <div className="rounded-3xl border border-dashed border-slate-300 bg-white/60 p-8 text-center">
              <p className="text-4xl">✦</p>
              <p className="mt-3 font-semibold">Your insights will appear here</p>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                We keep scores deterministic and use AI only where semantic
                understanding is useful.
              </p>
            </div>
          )}
        </section>
      </div>
    </main>
  );
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
      className="rounded-xl border border-slate-200 px-4 py-3 text-sm font-medium transition hover:border-indigo-300 hover:bg-indigo-50 disabled:cursor-not-allowed disabled:opacity-60"
    >
      {busy ? "Working..." : children}
    </button>
  );
}

function FeedbackPanel({
  title,
  items,
}: {
  title: string;
  items: FeedbackItem[];
}) {
  return (
    <div className="rounded-3xl border border-slate-200 bg-white p-6 shadow-sm">
      <h2 className="font-semibold">{title}</h2>
      <div className="mt-4 space-y-3">
        {items.map((item, index) => (
          <article
            key={`${item.section}-${index}`}
            className="rounded-2xl bg-slate-50 p-4"
          >
            <p className="text-xs font-semibold uppercase text-indigo-700">
              {item.section}
            </p>
            <p className="mt-1 text-sm font-medium">{item.point}</p>
            {item.evidence && (
              <p className="mt-2 text-sm text-slate-500">
                Evidence: {item.evidence}
              </p>
            )}
            {item.suggestion && (
              <p className="mt-2 text-sm text-slate-700">
                {item.suggestion}
              </p>
            )}
          </article>
        ))}
        {items.length === 0 && (
          <p className="text-sm text-slate-500">No findings returned.</p>
        )}
      </div>
    </div>
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
    emerald: "bg-emerald-50 text-emerald-700",
    rose: "bg-rose-50 text-rose-700",
    amber: "bg-amber-50 text-amber-700",
  };

  return (
    <div>
      <p className="mb-2 text-sm font-semibold">{title}</p>
      {skills.length > 0 ? (
        <div className="flex flex-wrap gap-2">
          {skills.map((skill) => (
            <span
              key={skill}
              className={`rounded-full px-3 py-1 text-xs font-medium ${styles[color]}`}
            >
              {skill}
            </span>
          ))}
        </div>
      ) : (
        <p className="text-sm text-slate-400">None detected</p>
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
