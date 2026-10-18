# GroundTruth: engineering notes

This document explains how the system is built, why, and what changes on the way to production.

## 1. Core decision: separate judgement from arithmetic

Insurance decisions must be reproducible, explainable and appealable. LLMs are excellent at
reading messy evidence (a phone photo, a note in Marathi) and at explaining outcomes in plain
language; they are not an acceptable source of payout numbers. The system is therefore split:

| Layer | Responsibility | Implementation | Determinism |
|---|---|---|---|
| Perception | Photo + note to typed facts (crop, peril, visible loss, translation) | Gemini 2.5 Flash, schema-constrained JSON | Bounded: typed, validated, temperature 0.1 |
| Evidence | Vegetation-index drop, rainfall anomaly, inundation for the insured area | `engine.evidence_for` | Fully deterministic |
| Adjudication | Covered peril, intimation window, 33% threshold, corroboration, loss cap, top-up survey, payout | `engine.adjudicate` | Fully deterministic, unit-tested |
| Explanation | Farmer message in their language + assessor summary citing clauses | Gemini, facts-only prompt | Cannot change the decision |

The model never writes a number into the decision. If Gemini is unavailable, both agents fall
back to deterministic behaviour; the explanation degrades, the verdict does not.

## 2. Fairness and fraud as first-class rules

- **Loss cap:** assessed loss never exceeds what remote sensing supports (`ndvi_drop x 1.3`).
- **Top-up survey:** if the farmer reports at least 15 points more than the satellite confirms,
  the proven part is paid now and a field survey is booked for the gap. Hail, pest and animal
  damage are often too local for 10 m imagery; the system must not silently cut genuine loss.
- **Mismatch routing:** a covered peril that satellite and rainfall data contradict goes to a
  physical survey, never to silent payment or silent rejection.
- **Photo integrity (`app/integrity.py`):** EXIF capture time and geotag are extracted, and a
  64-bit perceptual hash is checked against earlier claims in Firestore. The same photo used by
  different farmers is a classic fraud pattern; in production that routes to survey. Missing
  EXIF is recorded as an assessor note only, because messaging apps strip metadata.

## 3. Reliability

- Gemini calls declare a Pydantic response schema; output is validated again server-side.
- Per-call timeout (`GEMINI_TIMEOUT_MS`), bounded retries with exponential backoff and jitter
  (`GEMINI_MAX_ATTEMPTS`), then deterministic fallback. Attempts and model id are recorded.
- Intake (network bound) and photo integrity (CPU bound) run concurrently.
- Uploads are size-limited (6 MB) and type-checked by magic bytes, not by declared MIME type.

## 4. Auditability

Every claim document in Firestore carries the inputs, typed intake, evidence values, every rule
check with its clause id, the decision, the explanation, per-agent latency and attempts, the
engine version and the model id. Identical inputs produce identical decisions (tested).

## 5. Observability

Structured JSON logs to Cloud Logging with `logging.googleapis.com/trace` correlation from the
Cloud Run trace header, so one claim can be followed from request to decision. Each decision
logs the verdict and agent timings, which feed log-based metrics (latency, fallback rate,
verdict mix) and alerting.

## 6. Testing

- `tests/test_engine.py`: rule-level tests (payout formula, loss cap, top-up, fraud routing,
  late intimation, uncovered peril, determinism).
- `tests/test_api.py`: API contract with Gemini and Firestore disabled (fallback path), input
  validation, magic-byte upload rejection, audit trace completeness.
- `tests/test_integrity.py`: perceptual hash stability under resize and recompression, EXIF handling.
- `video/bench.py`: end-to-end benchmark against the live service (5/5 verdicts correct,
  median about 10 s including image upload and two model calls).
- `cloudbuild.yaml`: Cloud Build pipeline that runs the tests, builds, pushes and deploys.

## 7. Known limitations (prototype) and the production path

| Area | Prototype | Production |
|---|---|---|
| Evidence data | Synthetic, clearly labelled district signals | Earth Engine: Sentinel-2 NDVI per plot using field boundaries (e.g. AnthroKrishi), Sentinel-1 SAR change detection for floods under monsoon cloud, gridded rainfall (CHIRPS / national met data) |
| Granularity | District | Insured plot polygon; zonal statistics with cloud masking |
| Vision estimate | Single LLM estimate | Calibrated against a labelled photo set (crop-cutting ground truth); confidence bands; human review below a confidence threshold |
| Scheme rules | One model scheme in code | Versioned rule packs per programme (PMFBY, PCIC), clause text retrieved from Vertex AI Search, effective dating |
| Processing | Synchronous request (~10 s) | Async: Pub/Sub or Cloud Tasks queue, idempotency keys, claim status updates to the farmer by SMS/WhatsApp |
| Identity and access | Open demo | Farmer OTP auth, insurer roles via Identity Platform, least-privilege service accounts, VPC Service Controls |
| Data protection | Demo data | PII minimisation, retention policy, CMEK, audit logs, regional data residency per country |
| Tenancy | Single tenant | Project or database per insurer, provisioned with Terraform |
| Evaluation | Benchmark of 5 scenarios | Offline eval set per crop and peril; precision/recall of fraud routing; payout error vs. surveyed loss; drift monitoring |

## 8. Why this stack

Cloud Run gives scale-to-zero for a seasonal, spiky workload (claims arrive in bursts after an
event). Firestore holds variable-shape evidence packs without migrations and supports
per-document audit. Gemini on Vertex AI provides multimodal, multilingual perception and
explanation inside the same project boundary and IAM model as the data.
