# GroundTruth

**Crop-loss claims verified from space in minutes, not months.**

When a flood, drought or typhoon hits, smallholder farmers across Asia-Pacific often wait months for crop-insurance payouts. Manual field surveys are slow, disputes are common, and fraud raises costs for everyone. GroundTruth lets a farmer file a claim with a phone photo and a voice-style note in their own language. A team of agents then checks the claim against satellite and weather evidence and settles it under the scheme rules in under a minute, with every number traceable.

**Live prototype:** https://groundtruth-673378516921.asia-south1.run.app  
**Demo video (3 min):** https://groundtruth-673378516921.asia-south1.run.app/static/GroundTruth_Demo.mp4  
**Engineering notes:** [ENGINEERING.md](ENGINEERING.md) · **Deck:** [GroundTruth_Deck.pdf](GroundTruth_Deck.pdf) · **How it works:** https://groundtruth-673378516921.asia-south1.run.app/static/arch.html

## Results on the live service

| Scenario | Expected | Verdict | Assessed loss | Language |
|---|---|---|---|---|
| Flood, Assam | APPROVE | APPROVE | 77% | Hindi |
| Drought, Maharashtra | APPROVE | APPROVE + top-up survey | 52.8% paid now, survey for the rest | Marathi |
| Typhoon, Philippines | APPROVE | APPROVE | 67.9% | Filipino |
| "Total flood loss", Punjab, normal rainfall | SURVEY | SURVEY (fraud flag) | 0% | English |
| Flood reported after 20 days | REJECT | REJECT | n/a | English |

5/5 correct verdicts; median about 10 s end to end per claim, including photo upload and two Gemini calls. Reproduce with `python3 video/bench.py <service-url>`.

## How it works

| Step | Agent | What it does | Runs on |
|---|---|---|---|
| 1 | Intake Agent | Reads the field photo and the note (any language): crop, peril, visible loss, translation | Gemini 2.5 Flash (Vertex AI), multimodal |
| 2 | Evidence Agent | Pulls the district's vegetation-index drop and rainfall anomaly for the event window and decides whether the evidence corroborates the claim | Deterministic engine |
| 3 | Policy + Adjudicator | Applies the scheme clauses (covered peril, 33% threshold, 7-day intimation, corroboration, payout formula) and returns APPROVE / SURVEY / REJECT with the clauses cited | Deterministic rules engine |
| 4 | Explainer Agent | Writes the verdict for the farmer (in their language) and for the assessor, using only the engine's facts | Gemini 2.5 Flash |

Every claim, with its full evidence pack and agent trace, is stored in **Cloud Firestore** (Firebase). The app runs on **Cloud Run**.

**Design principle: the AI explains; a deterministic engine proves.** The model never sets a number. The assessed loss is capped by what the satellite supports, so a dramatic photo cannot outrun the evidence; and when the farmer reports clearly more than the satellite can confirm (hail, pests and animal damage are often too local), the proven part is paid now and a field survey is booked automatically for the rest. Claims that the data contradicts are flagged and routed to a physical survey.

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

## Demo assets

`video/gen_samples.py` generates the sample field photos with Gemini image generation, `video/make_video.py` records the narrated demo (Cloud Text-to-Speech + Playwright against the live service), `video/build_deck.py` fills the official submission template.

## Repository layout

```
app/engine.py   deterministic evidence + adjudication
app/agents.py   Gemini intake + explainer agents: schema-constrained output, retries, fallbacks
app/integrity.py photo EXIF + perceptual-hash duplicate detection
app/main.py     FastAPI service, Firestore claim store
static/         web UI
tests/          engine, API contract and integrity tests (15)
cloudbuild.yaml test, build and deploy pipeline
```
