"""Gemini-powered agents. They read, interpret and explain; they never set numbers.

Each agent has a deterministic fallback so the demo never breaks if the
model is unavailable.
"""
from __future__ import annotations

import json
import os
import re

MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash")
_client = None


def _gemini():
    global _client
    if _client is None:
        from google import genai
        _client = genai.Client(
            vertexai=True,
            project=os.getenv("GOOGLE_CLOUD_PROJECT"),
            location=os.getenv("GEMINI_LOCATION", "us-central1"),
        )
    return _client


def _json(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    return json.loads(m.group(0)) if m else {}


PERILS = ["flood", "drought", "hail", "cyclone", "pest", "none"]


def intake_agent(note: str, image_bytes: bytes | None, mime: str | None) -> dict:
    """Vision + language intake: what crop, what damage, how bad, in what language."""
    prompt = (
        "You are the Intake Agent for a crop-insurance claim desk. A smallholder farmer "
        "has sent a field photo and a short note (any language). Return ONLY JSON with keys: "
        "crop (one word, english), peril (one of " + ", ".join(PERILS) + "), "
        "field_loss_pct (0-100 integer, your visual estimate of crop loss in the photo), "
        "visual_evidence (one sentence describing what the photo shows), "
        "language (the note's language name), note_english (faithful english translation). "
        "If the photo shows a healthy crop, set field_loss_pct low and say so.\n\nFarmer note: " + note
    )
    try:
        from google.genai import types
        parts = [prompt]
        if image_bytes:
            if image_bytes[:4] == b"\x89PNG":
                mime = "image/png"
            elif image_bytes[:3] == b"\xff\xd8\xff":
                mime = "image/jpeg"
            parts.append(types.Part.from_bytes(data=image_bytes, mime_type=mime or "image/jpeg"))
        r = _gemini().models.generate_content(
            model=MODEL, contents=parts,
            config=types.GenerateContentConfig(temperature=0.1, response_mime_type="application/json"))
        out = _json(r.text)
        out["peril"] = out.get("peril", "none") if out.get("peril") in PERILS else "none"
        out["field_loss_pct"] = max(0, min(100, int(out.get("field_loss_pct", 0))))
        out["source"] = "gemini"
        return out
    except Exception as e:  # deterministic fallback
        low = note.lower()
        peril = next((p for p in ["flood", "drought", "hail", "cyclone", "pest"] if p in low), "none")
        return {"crop": "paddy", "peril": peril, "field_loss_pct": 50 if peril != "none" else 5,
                "visual_evidence": "Fallback: photo not analysed.", "language": "unknown",
                "note_english": note, "source": f"fallback ({type(e).__name__})"}


def explainer_agent(decision: dict, intake: dict, evidence: dict) -> dict:
    """Writes the farmer-facing and assessor-facing explanation from the engine's facts."""
    facts = json.dumps({"decision": decision, "intake": intake, "evidence": evidence}, default=str)
    lang = intake.get("language") or "English"
    prompt = (
        "You are the Explainer Agent. Using ONLY the facts below (do not invent or change any "
        "number), return JSON with keys: farmer_message (3 short sentences in " + lang +
        ", plain words, state the verdict, amount if any, and the next step), "
        "assessor_summary (2 sentences in English citing clause ids like [C2]).\n\nFACTS: " + facts
    )
    try:
        from google.genai import types
        r = _gemini().models.generate_content(
            model=MODEL, contents=prompt,
            config=types.GenerateContentConfig(temperature=0.2, response_mime_type="application/json"))
        out = _json(r.text)
        out["source"] = "gemini"
        return out
    except Exception as e:
        v = decision["verdict"]
        msg = {"APPROVE": f"Your claim is approved. Payout: {decision['payout']}.",
               "SURVEY": "Your claim needs a field survey before settlement.",
               "REJECT": "Your claim could not be approved under the scheme rules."}[v]
        return {"farmer_message": msg, "assessor_summary": f"Verdict {v} by rules engine.",
                "source": f"fallback ({type(e).__name__})"}
