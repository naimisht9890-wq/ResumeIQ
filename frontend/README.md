# ResumeIQ frontend

The ResumeIQ web workspace is built with Next.js, React, TypeScript, and
Tailwind CSS. It connects to the FastAPI service in the repository root.

## Run locally

1. Install the Python dependencies from the repository root and configure
   `GROQ_API_KEY` in the root `.env` file.
2. In one terminal, start the API from the repository root:

   ```bash
   uvicorn app.main:app --reload
   ```

3. In a second terminal, start the job worker from the repository root:

   ```bash
   python -m app.worker
   ```

   Keep one worker process running. The API queues parsing and analysis jobs;
   the worker executes them and saves their results for the frontend to poll.
   Use `python -m app.worker --once` to process at most one queued job and exit.

4. Install frontend dependencies and start Next.js:

   ```bash
   cd frontend
   npm install
   npm run dev
   ```

The frontend uses `http://127.0.0.1:8000` by default. To use another API
address, set `NEXT_PUBLIC_API_BASE_URL` in the frontend environment before
starting or building the app.

Job records and completed results are stored in `data/resumeiq.sqlite3` by
default. Set `RESUMEIQ_DATABASE_PATH` to move the database. Queued request
payloads are removed after a job completes or fails; completed and failed
results are eligible for cleanup after seven days when the worker is running.
The local database is ignored by Git and may contain personal resume data in
job results; restrict access to the database file and its backups.

Curated guidance from `knowledge/resume_best_practices.json` is indexed in the
same SQLite database using FTS5 and ranked with BM25, filtered by rule
category. The index refreshes automatically when the JSON corpus changes.
Generated feedback, tailoring, cover-letter, and ATS responses include
citations for retrieved rules. ATS scores remain deterministic; retrieved ATS
guidance is shown as context and does not change the numeric score.

## Workspace features

- Upload a PDF, DOCX, or TXT resume by browsing or dragging it into the drop
  area, then paste a target job description.
- View the ATS compatibility score, its component scores and scoring notes,
  and the required/preferred skill gaps.
- Generate strengths and improvement feedback, review and accept/reject
  resume-tailoring suggestions, create a cover-letter draft, and download an
  ATS-friendly DOCX.

## Checks

```bash
npm run lint
npm run build
```
