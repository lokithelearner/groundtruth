# GroundTruth

**Crop-loss claims verified from space in minutes, not months.**

When a flood, drought or typhoon hits, smallholder farmers across Asia-Pacific often wait months for crop-insurance payouts. Manual field surveys are slow, disputes are common, and fraud raises costs for everyone. GroundTruth lets a farmer file a claim with a phone photo and a voice-style note in their own language. A team of agents then checks the claim against satellite and weather evidence and settles it under the scheme rules in under a minute, with every number traceable.

## How it works

| Step | Agent | What it does | Runs on |
|---|---|---|---|
| 1 | Intake Agent | Reads the field photo and the note (any language): crop, peril, visible loss, translation | Gemini 2.5 Flash (Vertex AI), multimodal |
| 2 | Evidence Agent | Pulls the district's vegetation-index drop and rainfall anomaly for the event window and decides whether the evidence corroborates the claim | Deterministic engine |
| 3 | Policy + Adjudicator | Applies the scheme clauses (covered peril, 33% threshold, 7-day intimation, corroboration, payout formula) and returns APPROVE / SURVEY / REJECT with the clauses cited | Deterministic rules engine |
| 4 | Explainer Agent | Writes the verdict for the farmer (in their language) and for the assessor, using only the engine's facts | Gemini 2.5 Flash |

Every claim, with its full evidence pack and agent trace, is stored in **Cloud Firestore** (Firebase). The app runs on **Cloud Run**.

**Design principle: the AI explains; a deterministic engine proves.** The model never sets a number. The assessed loss is capped by what the satellite supports, so a dramatic photo cannot outrun the evidence. Claims that the data contradicts are flagged and routed to a physical survey.

## Demo scenarios

- Flooded paddy, Assam (Hindi note) → approved with payout
- Dry cotton, Maharashtra (Marathi note) → approved, loss capped by satellite
- Typhoon-hit rice, Philippines (Filipino note) → approved
- "Total flood loss" in Punjab with a healthy-field photo and normal rainfall → flagged, sent to survey

Satellite and rainfall values in this prototype are **synthetic sample signals**, clearly labelled, shaped like the series an insurer would pull from Earth Engine and a weather API. The scheme is a model scheme based on common area-yield crop-insurance rules.

## Run locally

```bash
pip install -r requirements.txt
DISABLE_FIRESTORE=1 uvicorn app.main:app --reload   # Gemini falls back to rules if no credentials
pytest -q
```

## Deploy

```bash
gcloud services enable run.googleapis.com aiplatform.googleapis.com firestore.googleapis.com cloudbuild.googleapis.com
gcloud firestore databases create --location=asia-south1   # once
gcloud run deploy groundtruth --source . --region asia-south1 --allow-unauthenticated \
  --set-env-vars GOOGLE_CLOUD_PROJECT=$(gcloud config get-value project)
```

The Cloud Run service account needs `roles/aiplatform.user` and `roles/datastore.user`.

## Roadmap

Live Earth Engine (Sentinel-2) and rainfall feeds per insured plot · voice intake via Speech-to-Text · Vertex AI Search over each country's scheme documents · insurer console with survey queue · multi-tenant deployment per insurer.

## Repository layout

```
app/engine.py   deterministic evidence + adjudication
app/agents.py   Gemini intake + explainer agents (with fallbacks)
app/main.py     FastAPI service, Firestore claim store
static/         web UI
tests/          engine tests
```
