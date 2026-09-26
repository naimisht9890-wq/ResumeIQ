import logging
import os
from contextlib import asynccontextmanager
from threading import Event, Thread
from typing import AsyncGenerator

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.router import api_router
from dotenv import load_dotenv
from app.worker import run_worker


load_dotenv()

LOGGER = logging.getLogger("resumeiq.api")


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncGenerator[None, None]:
    worker_mode = os.getenv("RESUMEIQ_WORKER_MODE", "embedded").strip().lower()
    if worker_mode not in {"embedded", "external"}:
        raise RuntimeError(
            "RESUMEIQ_WORKER_MODE must be 'embedded' or 'external'."
        )

    worker_stop = Event()
    worker_thread: Thread | None = None
    if worker_mode == "embedded":
        worker_thread = Thread(
            target=run_worker,
            kwargs={"stop_event": worker_stop},
            name="resumeiq-job-worker",
            daemon=True,
        )
        worker_thread.start()
        LOGGER.info("Started embedded ResumeIQ job worker.")
    else:
        LOGGER.info(
            "Embedded job worker disabled; start `python -m app.worker` "
            "as a separate process."
        )

    try:
        yield
    finally:
        if worker_thread is not None:
            worker_stop.set()
            worker_thread.join(timeout=10)
            if worker_thread.is_alive():
                LOGGER.warning(
                    "ResumeIQ job worker is still finishing a job during "
                    "API shutdown."
                )


app = FastAPI(
    title="ResumeIQ",
    version="0.1.0",
    lifespan=lifespan,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(api_router)
