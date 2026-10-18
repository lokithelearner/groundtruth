"""GroundTruth API: crop-loss claims verified from space in minutes, not months."""
from __future__ import annotations

import asyncio
import json
import logging
import os
import sys
import time
import uuid
from datetime import datetime, timezone

from fastapi import FastAPI, File, Form, HTTPException, Request, UploadFile
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import agents, engine, integrity
from .data import DISTRICTS

ENGINE_VERSION = "1.2.0"
PROJECT = os.getenv("GOOGLE_CLOUD_PROJECT", "")


class _JsonLog(logging.Formatter):
    """Cloud Logging structured format: severity, message, trace correlation, extra fields."""
    def format(self, r):
        d = {"severity": r.levelname, "message": r.getMessage(), "logger": r.name}
        for k in ("trace", "claim_id", "latency_ms", "path", "status", "verdict", "agents"):
            if hasattr(r, k):
                d["logging.googleapis.com/trace" if k == "trace" else k] = getattr(r, k)
        return json.dumps(d, default=str)


_h = logging.StreamHandler(sys.stdout); _h.setFormatter(_JsonLog())
logging.basicConfig(level=logging.INFO, handlers=[_h], force=True)
log = logging.getLogger("groundtruth")

app = FastAPI(title="GroundTruth", version=ENGINE_VERSION)


def _trace(request: Request) -> str | None:
    h = request.headers.get("x-cloud-trace-context", "")
    return f"projects/{PROJECT}/traces/{h.split('/')[0]}" if h and PROJECT else None


@app.middleware("http")
async def access_log(request: Request, call_next):
    t = time.time()
    resp = await call_next(request)
    if request.url.path.startswith("/api/"):
        log.info("request", extra={"trace": _trace(request), "path": request.url.path,
                                    "status": resp.status_code, "latency_ms": int((time.time() - t) * 1000)})
    return resp
from fastapi.middleware.cors import CORSMiddleware
app.add_middleware(CORSMiddleware, allow_origins=["https://hack2skill.com", "https://www.hack2skill.com"], allow_methods=["GET"])
STATIC = os.path.join(os.path.dirname(__file__), "..", "static")
MAX_IMAGE = 6 * 1024 * 1024
_db = None


def db():
    """Firestore (Firebase) claim store; None if unavailable (local dev)."""
    global _db
    if _db is None and os.getenv("DISABLE_FIRESTORE") != "1":
        try:
            from google.cloud import firestore
            _db = firestore.Client()
        except Exception:
            _db = False
    return _db or None


@app.get("/api/health")
def health():
    return {"ok": True, "firestore": bool(db()), "model": agents.MODEL, "engine_version": ENGINE_VERSION}


@app.get("/api/districts")
def districts():
    return [{"id": k, "name": v["name"], "event": v["event"]} for k, v in DISTRICTS.items()]


@app.post("/api/claims")
async def create_claim(
    request: Request,
    district: str = Form(...),
    acres: float = Form(...),
    days_since_event: int = Form(...),
    note: str = Form(""),
    farmer: str = Form("Farmer"),
    photo: UploadFile | None = File(None),
):
    if district not in DISTRICTS:
        raise HTTPException(400, "Unknown district")
    if not (0 < acres <= 50) or not (0 <= days_since_event <= 60):
        raise HTTPException(400, "Acres must be 0-50 and days 0-60")
    note = note[:600]
    image = mime = None
    if photo is not None and photo.filename:
        image = await photo.read()
        if len(image) > MAX_IMAGE:
            raise HTTPException(413, "Photo too large")
        mime = photo.content_type
        if image[:4] != b"\x89PNG" and image[:3] != b"\xff\xd8\xff" and image[:4] != b"RIFF":
            raise HTTPException(415, "Photo must be JPEG, PNG or WebP")

    claim_id = "GT-" + uuid.uuid4().hex[:6].upper()
    trace = []
    t = time.time()
    # Intake (Gemini, I/O bound) and photo integrity analysis run concurrently.
    intake, photo_info = await asyncio.gather(
        asyncio.to_thread(agents.intake_agent, note, image, mime),
        asyncio.to_thread(integrity.analyse, image))
    trace.append({"agent": "Intake Agent", "model": intake.get("source"), "attempts": intake.get("attempts"),
                  "ms": int((time.time() - t) * 1000)})
    store = db()
    photo_info["duplicates"] = await asyncio.to_thread(
        integrity.duplicate_check, store, photo_info.get("phash"), claim_id, farmer[:60])

    t = time.time()
    ev = engine.evidence_for(district, intake["peril"])
    trace.append({"agent": "Evidence Agent", "model": "deterministic (satellite + rainfall)", "ms": int((time.time() - t) * 1000)})

    t = time.time()
    dec = engine.adjudicate(crop=intake.get("crop", "other"), acres=acres, claimed_peril=intake["peril"],
                            field_loss_pct=intake["field_loss_pct"], days_since_event=days_since_event, ev=ev)
    trace.append({"agent": "Policy + Adjudicator", "model": "deterministic rules engine", "ms": int((time.time() - t) * 1000)})

    t = time.time()
    expl = agents.explainer_agent(engine.as_dict(dec), intake, engine.as_dict(ev))
    trace.append({"agent": "Explainer Agent", "model": expl.get("source"), "attempts": expl.get("attempts"),
                  "ms": int((time.time() - t) * 1000)})

    claim = {
        "id": claim_id, "engine_version": ENGINE_VERSION, "model": agents.MODEL, "integrity": photo_info,
        "created": datetime.now(timezone.utc).isoformat(),
        "farmer": farmer[:60], "district": district, "acres": acres,
        "days_since_event": days_since_event, "note": note,
        "intake": intake, "evidence": engine.as_dict(ev), "decision": engine.as_dict(dec),
        "explanation": expl, "trace": trace,
    }
    if store:
        try:
            store.collection("claims").document(claim["id"]).set(claim)
            claim["stored"] = "firestore"
        except Exception as e:
            claim["stored"] = f"not stored ({type(e).__name__})"
    log.info("claim decided", extra={"trace": _trace(request), "claim_id": claim_id, "verdict": dec.verdict,
                                     "agents": trace})
    return JSONResponse(claim)


@app.get("/api/claims")
def list_claims():
    store = db()
    if not store:
        return []
    from google.cloud import firestore
    docs = store.collection("claims").order_by("created", direction=firestore.Query.DESCENDING).limit(12).stream()
    out = []
    for d in docs:
        c = d.to_dict()
        out.append({"id": c["id"], "farmer": c.get("farmer"), "district": DISTRICTS.get(c["district"], {}).get("name"),
                    "verdict": c["decision"]["verdict"], "payout": c["decision"]["payout"], "created": c["created"]})
    return out


app.mount("/static", StaticFiles(directory=STATIC), name="static")


@app.get("/")
def index():
    return FileResponse(os.path.join(STATIC, "index.html"))
