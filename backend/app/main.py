import asyncio
import hmac
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Annotated

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse
from fastapi.security import HTTPBasic, HTTPBasicCredentials
from pydantic import BaseModel, Field

from .jdownloader import CNLClient, JDownloaderUnavailable
from .resolver import RedirectResolver
from .security import UnsafeURL, normalize_url, validate_destination
from .settings import Settings
from .store import JobStore

log = logging.getLogger("jfstack.downloader")
logging.basicConfig(level=logging.INFO)
settings = Settings.from_env()
store = JobStore(settings.database_path)
resolver = RedirectResolver(settings.request_timeout, settings.max_hops)
client = CNLClient(settings.cnl_url)
security = HTTPBasic()


async def require_auth(credentials: Annotated[HTTPBasicCredentials, Depends(security)]):
    correct_user = hmac.compare_digest(credentials.username.encode(), settings.username.encode())
    correct_password = hmac.compare_digest(credentials.password.encode(), settings.password.encode())
    if not (correct_user and correct_password):
        raise HTTPException(status_code=401, detail="Invalid credentials",
                            headers={"WWW-Authenticate": "Basic"})
    return credentials.username


async def process_job(job: dict) -> None:
    job_id = job["id"]
    try:
        await validate_destination(job["original_url"])
        resolved = await resolver.resolve(job["original_url"])
        await validate_destination(resolved.url)
        if resolved.needs_manual:
            store.update(job_id, "manual", resolved.url, resolved.method, resolved.note)
            return
        try:
            await client.send(resolved.url)
        except JDownloaderUnavailable as exc:
            store.update(job_id, "ready", resolved.url, resolved.method, str(exc))
            return
        store.update(job_id, "sent", resolved.url, resolved.method,
                     resolved.note + "; submitted to LinkGrabber (not a download confirmation)")
    except UnsafeURL as exc:
        store.update(job_id, "error", note=str(exc))
    except Exception:
        log.exception("Unexpected job failure (job id=%s)", job_id)
        store.update(job_id, "error", note="Unexpected processing error; inspect server logs")


async def worker_loop() -> None:
    while True:
        try:
            job = store.next_job()
            if job:
                await process_job(job)
            else:
                await asyncio.sleep(1)
        except asyncio.CancelledError:
            raise
        except Exception:
            log.exception("Worker failure")
            await asyncio.sleep(2)


@asynccontextmanager
async def lifespan(_: FastAPI):
    store.initialize()
    workers = [asyncio.create_task(worker_loop(), name=f"resolver-{i}")
               for i in range(settings.worker_count)]
    try:
        yield
    finally:
        for worker in workers:
            worker.cancel()
        await asyncio.gather(*workers, return_exceptions=True)


app = FastAPI(title="JFStack Downloader", version="0.1.0", docs_url=None,
              redoc_url=None, openapi_url=None, lifespan=lifespan)


@app.middleware("http")
async def protect_mutations(request: Request, call_next):
    if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
        if request.headers.get("content-type", "").split(";", 1)[0].lower() != "application/json":
            return JSONResponse({"detail": "application/json required"}, status_code=415)
        if request.headers.get("x-jfstack-request") != "1":
            return JSONResponse({"detail": "X-JFStack-Request: 1 required"}, status_code=403)
        origin = request.headers.get("origin")
        if origin:
            # Only same-origin browser requests may mutate. CLI with custom header works without Origin.
            host = request.headers.get("host", "")
            from urllib.parse import urlsplit
            if urlsplit(origin).netloc.lower() != host.lower() or urlsplit(origin).scheme not in {"http", "https"}:
                return JSONResponse({"detail": "Cross-origin request blocked"}, status_code=403)
    return await call_next(request)


class AddLinks(BaseModel):
    links: str = Field(min_length=1, max_length=200_000)


@app.get("/", dependencies=[Depends(require_auth)])
async def index():
    return FileResponse(Path(__file__).parents[1] / "static" / "index.html",
                        headers={"Cache-Control": "no-store", "X-Content-Type-Options": "nosniff",
                                 "Content-Security-Policy": "default-src 'self'; script-src 'self'; style-src 'self'; img-src 'self' data:; object-src 'none'; frame-ancestors 'none'; base-uri 'none'"})


@app.get("/static/app.js", dependencies=[Depends(require_auth)])
async def javascript():
    return FileResponse(Path(__file__).parents[1] / "static" / "app.js", media_type="text/javascript",
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-cache"})


@app.get("/static/style.css", dependencies=[Depends(require_auth)])
async def stylesheet():
    return FileResponse(Path(__file__).parents[1] / "static" / "style.css", media_type="text/css",
                        headers={"X-Content-Type-Options": "nosniff", "Cache-Control": "no-cache"})


@app.get("/healthz")
async def healthz():
    return {"status": "ok"}


@app.get("/api/status", dependencies=[Depends(require_auth)])
async def status():
    return {"jdownloader_cnl_ready": await client.is_ready(), "max_batch": settings.max_batch,
            "integration": "local-clicknload", "version": app.version}


@app.get("/api/jobs", dependencies=[Depends(require_auth)])
async def list_jobs(limit: int = 100):
    return {"jobs": store.list_jobs(max(1, min(limit, 200)))}


@app.post("/api/jobs", status_code=201, dependencies=[Depends(require_auth)])
async def add_jobs(body: AddLinks):
    urls = list(dict.fromkeys(line.strip() for line in body.links.splitlines() if line.strip()))
    if not urls or len(urls) > settings.max_batch:
        raise HTTPException(422, f"Provide between 1 and {settings.max_batch} URLs, one per line")
    for url in urls:
        try:
            normalize_url(url)
        except UnsafeURL as exc:
            raise HTTPException(422, f"Invalid URL in batch: {exc}") from exc
    return {"jobs": store.add_many(urls)}


@app.post("/api/jobs/{job_id}/retry", dependencies=[Depends(require_auth)])
async def retry_job(job_id: str):
    if not store.reset(job_id):
        raise HTTPException(409, "Job missing or not retryable")
    return {"status": "queued"}


@app.post("/api/jobs/{job_id}/send", dependencies=[Depends(require_auth)])
async def send_job(job_id: str):
    item = store.get(job_id)
    if not item:
        raise HTTPException(404, "Job not found")
    if item["status"] not in {"manual", "ready", "error"}:
        raise HTTPException(409, "Job cannot be submitted in this state")
    target = item["final_url"] or item["original_url"]
    try:
        await validate_destination(target)
        await client.send(target)
    except UnsafeURL as exc:
        raise HTTPException(422, str(exc)) from exc
    except JDownloaderUnavailable as exc:
        raise HTTPException(503, str(exc)) from exc
    store.update(job_id, "sent", target, "manual-submit", "Sent by user to LinkGrabber (not a download confirmation)")
    return {"status": "sent"}
