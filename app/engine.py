"""Deterministic evidence + adjudication engine.

The LLM agents describe and explain. Every number and every verdict is
produced here, from the claim facts and reference data, so the result is
reproducible and auditable.
"""
from __future__ import annotations

from dataclasses import dataclass, asdict, field

from .data import (DISTRICTS, POLICY_CLAUSES, SUM_INSURED_PER_ACRE,
                   LOSS_THRESHOLD, DEDUCTIBLE, INTIMATION_DAYS)

COVERED_PERILS = {"flood", "drought", "hail", "cyclone"}


@dataclass
class Evidence:
    district: str
    event: str
    data_peril: str
    rain_anomaly_pct: float
    ndvi_before: float
    ndvi_after: float
    ndvi_drop_pct: float
    inundation_days: int
    corroborates: bool
    signals: list = field(default_factory=list)


def evidence_for(district_id: str, claimed_peril: str) -> Evidence:
    d = DISTRICTS[district_id]
    rain_anom = round((d["rain_mm_observed"] - d["rain_mm_normal"]) / d["rain_mm_normal"] * 100, 1)
    ndvi_drop = round((d["ndvi_before"] - d["ndvi_after"]) / d["ndvi_before"] * 100, 1)
    signals = []
    if rain_anom >= 60:
        signals.append(f"Rainfall {rain_anom:+.0f}% vs normal (excess)")
    elif rain_anom <= -40:
        signals.append(f"Rainfall {rain_anom:+.0f}% vs normal (deficit)")
    else:
        signals.append(f"Rainfall {rain_anom:+.0f}% vs normal (within range)")
    signals.append(f"Vegetation index {d['ndvi_before']:.2f} -> {d['ndvi_after']:.2f} ({-ndvi_drop:+.0f}%)")
    if d["inundation_days"]:
        signals.append(f"Standing water detected for {d['inundation_days']} days")

    peril = claimed_peril if claimed_peril != "cyclone" else "flood"
    corroborates = (
        ndvi_drop >= 20
        and ((peril == "flood" and rain_anom >= 60)
             or (peril == "drought" and rain_anom <= -40)
             or (peril == "hail" and ndvi_drop >= 25))
    )
    return Evidence(d["name"], d["event"], d["peril"], rain_anom, d["ndvi_before"],
                    d["ndvi_after"], ndvi_drop, d["inundation_days"], corroborates, signals)


@dataclass
class Decision:
    verdict: str            # APPROVE | SURVEY | REJECT
    assessed_loss_pct: float
    sum_insured: int
    payout: int
    checks: list
    clauses: list
    fraud_flag: bool


def adjudicate(*, crop: str, acres: float, claimed_peril: str, field_loss_pct: float,
               days_since_event: int, ev: Evidence) -> Decision:
    crop_key = crop.lower() if crop.lower() in SUM_INSURED_PER_ACRE else "other"
    sum_insured = int(round(SUM_INSURED_PER_ACRE[crop_key] * max(acres, 0)))

    # Assessed loss: field (photo) estimate capped by what satellite supports,
    # so a dramatic photo cannot outrun the remote-sensing evidence.
    sat_supported = min(100.0, ev.ndvi_drop_pct * 1.3)
    assessed = round(min(field_loss_pct, sat_supported) if ev.corroborates else 0.0, 1)

    checks = []
    def chk(name, ok, detail, clause):
        checks.append({"check": name, "pass": bool(ok), "detail": detail, "clause": clause})

    chk("Peril is covered", claimed_peril in COVERED_PERILS,
        f"Claimed peril: {claimed_peril}", "C1")
    chk("Intimated in time", days_since_event <= INTIMATION_DAYS,
        f"{days_since_event} day(s) after event (limit {INTIMATION_DAYS})", "C3")
    chk("Corroborated by satellite + weather", ev.corroborates,
        "; ".join(ev.signals), "C5")
    chk("Loss above threshold", assessed >= LOSS_THRESHOLD,
        f"Assessed {assessed:.0f}% (threshold {LOSS_THRESHOLD:.0f}%)", "C2")

    covered = claimed_peril in COVERED_PERILS
    fraud_flag = covered and not ev.corroborates
    all_pass = all(c["pass"] for c in checks)
    if all_pass:
        verdict = "APPROVE"
    elif not covered or days_since_event > INTIMATION_DAYS:
        verdict = "REJECT"
    elif not ev.corroborates:
        verdict = "SURVEY"
    else:
        verdict = "REJECT"

    payout = int(round(sum_insured * assessed / 100 * (1 - DEDUCTIBLE))) if verdict == "APPROVE" else 0
    used = sorted({c["clause"] for c in checks} | ({"C4"} if verdict == "APPROVE" else set()))
    clauses = [c for c in POLICY_CLAUSES if c["id"] in used]
    return Decision(verdict, assessed, sum_insured, payout, checks, clauses, fraud_flag)


def as_dict(obj):
    return asdict(obj)
