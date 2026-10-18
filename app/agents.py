"""Gemini-powered agents. They read, interpret and explain; they never set numbers.

Design notes
- Structured output: every call declares a JSON schema (Pydantic) so Gemini must return
  typed fields; the response is validated again on our side before use.
- Resilience: per-call timeout, bounded retries with exponential backoff and jitter, then a
  deterministic fallback, so a model outage degrades the explanation, never the decision.
- Provenance: each result carries `source` (model id or fallback reason) and `attempts`,
  which are written to the claim's audit trace in Firestore.
"""
from __future__ import annotations

import json
import logging
import os
import random
import time
from typing import Literal

from pydantic import BaseModel, Field, ValidationError

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
TIMEOUT_MS = int(os.getenv("GEMINI_TIMEOUT_MS", "25000"))
MAX_ATTEMPTS = int(os.getenv("GEMINI_MAX_ATTEMPTS", "3"))
log = logging.getLogger("groundtruth.agents")
_client = None

Peril = Literal["flood", "drought", "hail", "cyclone", "pest", "none"]
PERILS = ["flood", "drought", "hail", "cyclone", "pest", "none"]


class IntakeResult(BaseModel):
    crop: str = Field(description="One word, English, e.g. paddy, cotton, wheat")
    peril: Peril
    field_loss_pct: int = Field(ge=0, le=100, description="Visual estimate of crop loss in the photo")
    visual_evidence: str = Field(description="One sentence on what the photo shows")
    language: str = Field(description="Language of the farmer's note")
    note_english: str = Field(description="Faithful English translation of the note")


class Explanation(BaseModel):
    farmer_message: str
    assessor_summary: str


def _gemini():
    global _client
    if _client is None:
        from google import genai
        from google.genai import types
        _client = genai.Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GEMINI_LOCATION", "us-central1"),
            http_options=types.HttpOptions(timeout=TIMEOUT_MS),
        )
    return _client


def _call(contents, schema: type[BaseModel], temperature: float):
    """Schema-constrained Gemini call with retries. Returns (model_instance, attempts)."""
    from google.genai import types
    last = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            r = _gemini().models.generate_content(
                model=MODEL, contents=contents,
                config=types.GenerateContentConfig(
                    temperature=temperature, response_mime_type="application/json",
                    response_schema=schema))
            return schema.model_validate(json.loads(r.text)), attempt
        except (ValidationError, ValueError) as e:  # malformed output: retry
            last = e
        except Exception as e:  # transport / quota: retry with backoff
            last = e
        if attempt < MAX_ATTEMPTS:
            time.sleep(min(4.0, 0.5 * 2 ** (attempt - 1)) + random.random() * 0.25)
    log.warning("gemini call failed after %d attempts: %s", MAX_ATTEMPTS, type(last).__name__)
    raise last


def _sniff_mime(image_bytes: bytes, mime: str | None) -> str:
    if image_bytes[:4] == b"\x89PNG":
        return "image/png"
    if image_bytes[:3] == b"\xff\xd8\xff":
        return "image/jpeg"
    return mime or "image/jpeg"


def intake_agent(note: str, image_bytes: bytes | None, mime: str | None) -> dict:
    """Vision + language intake: what crop, what damage, how bad, in what language."""
    prompt = (
        "You are the Intake Agent for a crop-insurance claim desk. A smallholder farmer has "
        "sent a field photo and a short note (any language). Describe only what is visible; "
        "if the photo shows a healthy crop, set field_loss_pct low and say so.\n\nFarmer note: " + note)
    if not image_bytes:
        prompt += ("\n\nNo photo was provided. Set visual_evidence to 'No photo provided; "
                   "estimate based on the note only' and do not describe any image.")
    try:
        from google.genai import types
        parts = [prompt]
        if image_bytes:
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type=_sniff_mime(image_bytes, mime)))
        res, attempts = _call(parts, IntakeResult, 0.1)
        out = res.model_dump()
        out.update(source=MODEL, attempts=attempts)
        return out
    except Exception as e:  # deterministic fallback keeps the pipeline alive
        low = note.lower()
        peril = next((p for p in ["flood", "drought", "hail", "cyclone", "pest"] if p in low), "none")
        return {"crop": "paddy", "peril": peril, "field_loss_pct": 50 if peril != "none" else 5,
                "visual_evidence": "Fallback: photo not analysed.", "language": "unknown",
                "note_english": note, "source": f"fallback ({type(e).__name__})", "attempts": MAX_ATTEMPTS}


def explainer_agent(decision: dict, intake: dict, evidence: dict) -> dict:
    """Writes the farmer-facing and assessor-facing explanation from the engine's facts only."""
    facts = json.dumps({"decision": decision, "intake": intake, "evidence": evidence}, default=str)
    lang = intake.get("language") or "English"
    prompt = (
        "You are the Explainer Agent. Using ONLY the facts below (never invent or change a number), "
        "write farmer_message (3 short sentences in " + lang + ", plain words: verdict, amount if any, "
        "next step, and mention a booked survey if topup_survey is true) and assessor_summary "
        "(2 sentences in English citing clause ids like [C2]).\n\nFACTS: " + facts)
    try:
        res, attempts = _call(prompt, Explanation, 0.2)
        out = res.model_dump()
        out.update(source=MODEL, attempts=attempts)
        return out
    except Exception as e:
        v = decision["verdict"]
        msg = {"APPROVE": f"Your claim is approved. Payout: {decision['payout']}.",
               "SURVEY": "Your claim needs a field survey before settlement.",
               "REJECT": "Your claim could not be approved under the scheme rules."}[v]
        return {"farmer_message": msg, "assessor_summary": f"Verdict {v} by rules engine.",
                "source": f"fallback ({type(e).__name__})", "attempts": MAX_ATTEMPTS}
