"""API contract tests. Gemini and Firestore are disabled, so the deterministic fallbacks run."""
import io
import os

os.environ.setdefault("DISABLE_FIRESTORE", "1")
os.environ.setdefault("GEMINI_MAX_ATTEMPTS", "1")
os.environ.setdefault("GOOGLE_CLOUD_PROJECT", "")

from fastapi.testclient import TestClient  # noqa: E402
from PIL import Image  # noqa: E402

from app.main import app  # noqa: E402

c = TestClient(app)


def _jpeg(color=(40, 120, 40)):
    b = io.BytesIO(); Image.new("RGB", (64, 48), color).save(b, "JPEG"); return b.getvalue()


def test_health_reports_versions():
    j = c.get("/api/health").json()
    assert j["ok"] and j["engine_version"] and j["model"]


def test_claim_contract_and_audit_trace():
    r = c.post("/api/claims", data={"district": "nagaon-in", "acres": 2, "days_since_event": 2,
                                    "note": "flood destroyed paddy"},
               files={"photo": ("f.jpg", _jpeg(), "image/jpeg")})
    assert r.status_code == 200
    j = r.json()
    assert j["id"].startswith("GT-") and j["engine_version"]
    assert {t["agent"] for t in j["trace"]} == {"Intake Agent", "Evidence Agent", "Policy + Adjudicator", "Explainer Agent"}
    assert j["decision"]["verdict"] in {"APPROVE", "SURVEY", "REJECT"}
    assert j["integrity"]["has_photo"] and len(j["integrity"]["phash"]) == 16


def test_rejects_non_image_upload():
    r = c.post("/api/claims", data={"district": "nagaon-in", "acres": 2, "days_since_event": 2, "note": "x"},
               files={"photo": ("f.jpg", b"not an image at all", "image/jpeg")})
    assert r.status_code == 415


def test_validates_inputs():
    assert c.post("/api/claims", data={"district": "nowhere", "acres": 2, "days_since_event": 2}).status_code == 400
    assert c.post("/api/claims", data={"district": "nagaon-in", "acres": 500, "days_since_event": 2}).status_code == 400
