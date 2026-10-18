from app import engine


def run(district, peril, loss, days=3, acres=2.0, crop="paddy"):
    ev = engine.evidence_for(district, peril)
    return ev, engine.adjudicate(crop=crop, acres=acres, claimed_peril=peril,
                                 field_loss_pct=loss, days_since_event=days, ev=ev)


def test_flood_claim_approved_with_payout():
    ev, d = run("nagaon-in", "flood", 85)
    assert ev.corroborates and d.verdict == "APPROVE"
    assert d.payout == round(d.sum_insured * d.assessed_loss_pct / 100 * 0.95)


def test_photo_cannot_exceed_satellite_support():
    ev, d = run("yavatmal-in", "drought", 100, crop="cotton")
    assert d.assessed_loss_pct <= round(ev.ndvi_drop_pct * 1.3, 1) + 0.1


def test_uncorroborated_claim_goes_to_survey_and_flags_fraud():
    _, d = run("ludhiana-in", "flood", 90, crop="wheat")
    assert d.verdict == "SURVEY" and d.fraud_flag and d.payout == 0


def test_late_intimation_rejected():
    _, d = run("nagaon-in", "flood", 85, days=20)
    assert d.verdict != "APPROVE" and d.payout == 0


def test_uncovered_peril_rejected():
    _, d = run("nagaon-in", "pest", 60)
    assert d.verdict == "REJECT"


def test_deterministic():
    assert run("isabela-ph", "flood", 70)[1] == run("isabela-ph", "flood", 70)[1]
