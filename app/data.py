"""Reference data for the GroundTruth demo.

All values below are SYNTHETIC sample signals, shaped to resemble the
satellite (vegetation index) and rainfall series an insurer would pull for a
district after a weather event. They are labelled as such in the UI.
"""

DISTRICTS = {
    "nagaon-in": {
        "name": "Nagaon, Assam (India)",
        "country": "India",
        "event": "Brahmaputra flood, Jul 2026",
        "peril": "flood",
        "rain_mm_normal": 410,
        "rain_mm_observed": 905,
        "ndvi_before": 0.71,
        "ndvi_after": 0.29,
        "inundation_days": 9,
    },
    "yavatmal-in": {
        "name": "Yavatmal, Maharashtra (India)",
        "country": "India",
        "event": "Monsoon deficit, Aug 2026",
        "peril": "drought",
        "rain_mm_normal": 290,
        "rain_mm_observed": 96,
        "ndvi_before": 0.64,
        "ndvi_after": 0.38,
        "inundation_days": 0,
    },
    "isabela-ph": {
        "name": "Isabela, Luzon (Philippines)",
        "country": "Philippines",
        "event": "Typhoon wind + flood, Sep 2026",
        "peril": "flood",
        "rain_mm_normal": 330,
        "rain_mm_observed": 760,
        "ndvi_before": 0.69,
        "ndvi_after": 0.33,
        "inundation_days": 5,
    },
    "ludhiana-in": {
        "name": "Ludhiana, Punjab (India)",
        "country": "India",
        "event": "No notified event in window",
        "peril": "none",
        "rain_mm_normal": 180,
        "rain_mm_observed": 171,
        "ndvi_before": 0.68,
        "ndvi_after": 0.66,
        "inundation_days": 0,
    },
}

# Model crop-insurance scheme (synthetic, modelled on common area-yield
# schemes across the region). Each clause is retrievable and cited.
POLICY_CLAUSES = [
    {"id": "C1", "title": "Covered perils",
     "text": "Localised calamities covered: flood/inundation, drought/dry spell, hailstorm, cyclone. Pest damage is covered only when notified by the district agriculture office."},
    {"id": "C2", "title": "Loss threshold",
     "text": "A claim is payable when assessed crop loss is 33% or more of expected yield."},
    {"id": "C3", "title": "Intimation window",
     "text": "Loss must be intimated within 7 days of the event becoming known."},
    {"id": "C4", "title": "Payout formula",
     "text": "Payout = Sum insured x assessed loss %, less a 5% deductible on the payout amount."},
    {"id": "C5", "title": "Corroboration",
     "text": "Field evidence must be corroborated by remote-sensing or weather data for the insured area. Contradicting evidence requires a physical survey before settlement."},
]

SUM_INSURED_PER_ACRE = {  # in local currency units, synthetic
    "paddy": 32000, "rice": 32000, "cotton": 38000, "wheat": 30000,
    "maize": 26000, "soybean": 28000, "sugarcane": 52000, "other": 25000,
}

LOSS_THRESHOLD = 33.0
DEDUCTIBLE = 0.05
INTIMATION_DAYS = 7
