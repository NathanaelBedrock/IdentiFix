from pathlib import Path
from fastapi import FastAPI, HTTPException, UploadFile, File, BackgroundTasks
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from sse_starlette.sse import EventSourceResponse

from core.config import settings
from core.models import Investigation, InvestigationCreateRequest, InvestigationTarget
from core.investigation import run_investigation
from workers.manager import store, event_stream
from reports.generator import generate_html_report
from collectors import ALL_COLLECTORS

app = FastAPI(title="IdentiFix", version="0.0.1")

# ── Static files ─────────────────────────────────────────────────────────────
static_dir = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    return (static_dir / "index.html").read_text()


# ── Investigations ────────────────────────────────────────────────────────────

@app.post("/api/investigations", response_model=dict)
async def create_investigation(
    req: InvestigationCreateRequest,
    background_tasks: BackgroundTasks,
):
    if not any([req.username, req.email, req.discord_id, req.twitter_handle, req.reddit_username]):
        raise HTTPException(status_code=422, detail="At least one target field is required")

    target = InvestigationTarget(
        username=req.username,
        email=req.email,
        discord_id=req.discord_id,
        twitter_handle=req.twitter_handle,
        reddit_username=req.reddit_username,
    )
    investigation = Investigation(target=target)
    store.save(investigation)
    background_tasks.add_task(run_investigation, investigation, store)
    return {"id": investigation.id, "status": investigation.status.value}


@app.get("/api/investigations", response_model=list[dict])
async def list_investigations():
    return [
        {
            "id": inv.id,
            "target": inv.target.label(),
            "status": inv.status.value,
            "created_at": inv.created_at.isoformat(),
            "summary": inv.summary(),
        }
        for inv in sorted(store.all(), key=lambda i: i.created_at, reverse=True)
    ]


@app.get("/api/investigations/{inv_id}")
async def get_investigation(inv_id: str):
    inv = store.get(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return inv.model_dump(mode="json")


@app.delete("/api/investigations/{inv_id}")
async def delete_investigation(inv_id: str):
    if not store.delete(inv_id):
        raise HTTPException(status_code=404, detail="Investigation not found")
    return {"deleted": True}


@app.get("/api/investigations/{inv_id}/report", response_class=HTMLResponse)
async def get_report(inv_id: str):
    inv = store.get(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return generate_html_report(inv)


@app.get("/api/investigations/{inv_id}/events")
async def investigation_events(inv_id: str):
    inv = store.get(inv_id)
    if not inv:
        raise HTTPException(status_code=404, detail="Investigation not found")
    return EventSourceResponse(event_stream(inv_id))


# ── Image upload ──────────────────────────────────────────────────────────────

@app.post("/api/upload-image", response_model=dict)
async def upload_image(file: UploadFile = File(...)):
    dest = settings.data_path / "images" / file.filename
    dest.parent.mkdir(parents=True, exist_ok=True)
    content = await file.read()
    dest.write_bytes(content)
    return {"path": str(dest), "filename": file.filename}


# ── Collector status ──────────────────────────────────────────────────────────

@app.get("/api/collectors")
async def list_collectors():
    return [
        {
            "name": cls.name,
            "available": cls.available(),
            "requires_username": cls.requires_username,
            "requires_email": cls.requires_email,
            "requires_image": cls.requires_image,
        }
        for cls in ALL_COLLECTORS
    ]


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host=settings.host, port=settings.port, reload=settings.debug)
