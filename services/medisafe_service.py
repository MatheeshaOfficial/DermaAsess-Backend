# services/medisafe_service.py
# Uses Hugging Face Inference API — no model loaded in Railway RAM
# microsoft/trocr-base-printed runs on HF servers

import io
import os
import re
import base64
import httpx
from PIL import Image, ImageEnhance

HF_TOKEN   = os.environ.get("HUGGINGFACE_API_TOKEN", "")
HF_HEADERS = {"Authorization": f"Bearer {HF_TOKEN}"}

# OCR model endpoint on Hugging Face
OCR_API_URL = (
    "https://api-inference.huggingface.co/models/"
    "microsoft/trocr-base-printed"
)
OCR_HW_URL = (
    "https://api-inference.huggingface.co/models/"
    "microsoft/trocr-base-handwritten"
)

# ── Drug database ─────────────────────────────────────────────
DRUG_DB = {
    "amoxicillin": {
        "class":        "Antibiotic (Penicillin)",
        "side_effects": [
            "Nausea and vomiting",
            "Diarrhea",
            "Skin rash",
            "Allergic reaction if penicillin allergy",
        ],
        "warnings": [
            "Do not take if allergic to penicillin",
            "Complete the full course",
            "Take with food to reduce nausea",
        ],
        "interactions":  ["Warfarin", "Methotrexate"],
        "allergy_flag":  "penicillin",
    },
    "azithromycin": {
        "class":        "Antibiotic (Macrolide)",
        "side_effects": ["Nausea", "Diarrhea", "Stomach pain"],
        "warnings":     ["Take 1hr before or 2hrs after antacids"],
        "interactions": ["Digoxin", "Warfarin"],
        "allergy_flag": None,
    },
    "ibuprofen": {
        "class":        "NSAID Anti-inflammatory",
        "side_effects": [
            "Stomach pain and ulcers",
            "Nausea",
            "Increased blood pressure",
        ],
        "warnings": [
            "Take with food",
            "Avoid if you have stomach ulcers",
        ],
        "interactions":  ["Aspirin", "Warfarin"],
        "allergy_flag":  "nsaids",
    },
    "paracetamol": {
        "class":        "Analgesic Antipyretic",
        "side_effects": [
            "Rare at normal doses",
            "Liver damage with overdose",
        ],
        "warnings":     ["Do not exceed 4g per day", "Avoid alcohol"],
        "interactions": ["Warfarin", "Alcohol"],
        "allergy_flag": None,
    },
    "metformin": {
        "class":        "Antidiabetic Biguanide",
        "side_effects": ["Nausea especially at start", "Diarrhea"],
        "warnings":     ["Take with meals"],
        "interactions": ["Alcohol", "Contrast dye"],
        "allergy_flag": None,
    },
    "omeprazole": {
        "class":        "Proton Pump Inhibitor",
        "side_effects": ["Headache", "Nausea", "Diarrhea"],
        "warnings":     ["Take 30-60 mins before meals"],
        "interactions": ["Clopidogrel", "Methotrexate"],
        "allergy_flag": None,
    },
    "atorvastatin": {
        "class":        "Statin Cholesterol lowering",
        "side_effects": ["Muscle pain and weakness", "Digestive issues"],
        "warnings": [
            "Report muscle pain immediately",
            "Avoid grapefruit juice",
        ],
        "interactions":  ["Warfarin", "Erythromycin"],
        "allergy_flag":  None,
    },
    "amlodipine": {
        "class":        "Calcium Channel Blocker",
        "side_effects": ["Ankle swelling", "Flushing", "Headache"],
        "warnings":     ["Do not stop suddenly", "Avoid grapefruit juice"],
        "interactions": ["Simvastatin", "Cyclosporine"],
        "allergy_flag": None,
    },
    "aspirin": {
        "class":        "NSAID Antiplatelet",
        "side_effects": ["Stomach bleeding", "Increased bleeding risk"],
        "warnings":     ["Never give to children under 16", "Take with food"],
        "interactions": ["Warfarin", "Ibuprofen"],
        "allergy_flag": "aspirin",
    },
    "warfarin": {
        "class":        "Anticoagulant Blood thinner",
        "side_effects": ["Bleeding risk", "Easy bruising"],
        "warnings": [
            "Regular blood tests required",
            "Tell all doctors you take warfarin",
        ],
        "interactions":  ["Aspirin", "Ibuprofen", "Many antibiotics"],
        "allergy_flag":  None,
    },
    "ciprofloxacin": {
        "class":        "Antibiotic Fluoroquinolone",
        "side_effects": [
            "Nausea", "Diarrhea",
            "Tendon pain especially Achilles",
            "Sensitivity to sunlight",
        ],
        "warnings":    ["Avoid sunlight", "Stop if tendon pain occurs"],
        "interactions": ["Antacids", "Warfarin"],
        "allergy_flag": None,
    },
    "salbutamol": {
        "class":        "Bronchodilator Inhaler",
        "side_effects": ["Trembling hands", "Fast heartbeat", "Headache"],
        "warnings":     ["Use as rescue inhaler only"],
        "interactions": ["Beta-blockers"],
        "allergy_flag": None,
    },
    "metronidazole": {
        "class":        "Antibiotic Antiprotozoal",
        "side_effects": ["Nausea", "Metallic taste", "Dizziness"],
        "warnings":     ["Avoid alcohol completely", "Take with food"],
        "interactions": ["Alcohol", "Warfarin", "Lithium"],
        "allergy_flag": None,
    },
    "cetirizine": {
        "class":        "Antihistamine",
        "side_effects": ["Drowsiness", "Dry mouth", "Headache"],
        "warnings":     ["May cause drowsiness — avoid driving"],
        "interactions": ["Alcohol", "Sedatives"],
        "allergy_flag": None,
    },
    "prednisolone": {
        "class":        "Corticosteroid",
        "side_effects": [
            "Weight gain", "Mood changes",
            "Increased blood sugar", "Weakened immune system",
        ],
        "warnings": [
            "Do not stop suddenly — taper dose",
            "Take with food",
            "Avoid contact with infections",
        ],
        "interactions":  ["NSAIDs", "Warfarin", "Diabetes medicines"],
        "allergy_flag":  None,
    },
}

ALIASES = {
    "tylenol": "paracetamol", "panadol": "paracetamol",
    "acetaminophen": "paracetamol", "calpol": "paracetamol",
    "advil": "ibuprofen", "nurofen": "ibuprofen", "brufen": "ibuprofen",
    "augmentin": "amoxicillin", "amoxil": "amoxicillin",
    "zithromax": "azithromycin", "azithral": "azithromycin",
    "cifran": "ciprofloxacin", "ciplox": "ciprofloxacin",
    "lipitor": "atorvastatin", "glucophage": "metformin",
    "prilosec": "omeprazole", "losec": "omeprazole",
    "norvasc": "amlodipine", "ventolin": "salbutamol",
    "flagyl": "metronidazole", "zyrtec": "cetirizine",
    "prednisone": "prednisolone",
}

DOSAGE_PATTERN = re.compile(
    r"(\d+(?:\.\d+)?)\s*(mg|ml|mcg|g|iu|units?|%)",
    re.IGNORECASE
)
FREQ_PATTERN = re.compile(
    r"\b(once|twice|thrice|od|bd|tds|qds|qid|tid|bid|"
    r"\d+\s*times?\s*(?:a|per)?\s*(?:day|daily|week)|"
    r"morning|night|evening|bedtime|every\s+\d+\s+hours?)\b",
    re.IGNORECASE
)
DURATION_PATTERN = re.compile(
    r"\b(\d+)\s*(days?|weeks?|months?)\b",
    re.IGNORECASE
)


def enhance_image(img: Image.Image) -> Image.Image:
    w, h = img.size
    if max(w, h) > 800:
        img.thumbnail((800, 800), Image.LANCZOS)
    img = ImageEnhance.Contrast(img).enhance(1.8)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    return img


async def run_ocr_api(image_bytes: bytes) -> str:
    """
    Send image to Hugging Face Inference API for OCR.
    Tries printed model first, then handwritten.
    No model loaded in Railway RAM.
    """
    # Enhance image first
    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = enhance_image(img)

    # Convert back to bytes for API
    buf = io.BytesIO()
    img.save(buf, format="JPEG", quality=95)
    enhanced_bytes = buf.getvalue()

    async with httpx.AsyncClient(timeout=60.0) as client:
        # Try printed model
        resp_pr = await client.post(
            OCR_API_URL,
            headers=HF_HEADERS,
            content=enhanced_bytes,
        )

        # Try handwritten model
        resp_hw = await client.post(
            OCR_HW_URL,
            headers=HF_HEADERS,
            content=enhanced_bytes,
        )

    text_pr = ""
    text_hw = ""

    if resp_pr.status_code == 200:
        result = resp_pr.json()
        # TrOCR returns list of dicts with "generated_text"
        if isinstance(result, list) and result:
            text_pr = result[0].get("generated_text", "")
        elif isinstance(result, dict):
            text_pr = result.get("generated_text", "")

    if resp_hw.status_code == 200:
        result = resp_hw.json()
        if isinstance(result, list) and result:
            text_hw = result[0].get("generated_text", "")
        elif isinstance(result, dict):
            text_hw = result.get("generated_text", "")

    # Return whichever has more content
    return text_pr if len(text_pr) >= len(text_hw) else text_hw


def parse_medicines(raw_text: str) -> list:
    medicines = []
    seen      = set()

    for line in raw_text.split("\n"):
        line = line.strip()
        if len(line) < 4:
            continue

        dosage_m   = DOSAGE_PATTERN.search(line)
        freq_m     = FREQ_PATTERN.search(line)
        duration_m = DURATION_PATTERN.search(line)

        if not dosage_m and not freq_m:
            continue

        name = line
        if dosage_m:
            name = line[:dosage_m.start()].strip()
        elif freq_m:
            name = line[:freq_m.start()].strip()

        name = re.sub(r"[^a-zA-Z0-9\s\-]", "", name).strip()
        name = " ".join(name.split())
        key  = name.lower()

        if len(name) >= 3 and key not in seen:
            seen.add(key)
            medicines.append({
                "name":      name,
                "dosage":    dosage_m.group(0)   if dosage_m   else "",
                "frequency": freq_m.group(0)     if freq_m     else "",
                "duration":  duration_m.group(0) if duration_m else "",
                "route":     "oral",
            })

    return medicines


def lookup_medicine(name: str) -> dict | None:
    key = name.lower().strip()
    if key in DRUG_DB:
        return DRUG_DB[key]
    if key in ALIASES:
        return DRUG_DB.get(ALIASES[key])
    for db_key in DRUG_DB:
        if db_key in key or key in db_key:
            return DRUG_DB[db_key]
    return None


async def analyze_prescription(
    image_bytes: bytes,
    user_allergies: list = None,
) -> dict:
    """Full prescription analysis — no RAM usage on Railway."""
    user_allergies       = user_allergies or []
    user_allergies_lower = [a.lower() for a in user_allergies]

    # OCR via Hugging Face API
    raw_text = await run_ocr_api(image_bytes)

    # Parse medicines
    medicines          = parse_medicines(raw_text)
    enriched           = []
    allergy_alerts     = []
    cross_interactions = []

    for med in medicines:
        info = lookup_medicine(med["name"])
        if info:
            if info.get("allergy_flag"):
                flag = info["allergy_flag"].lower()
                if any(flag in a for a in user_allergies_lower):
                    allergy_alerts.append(
                        f"ALLERGY ALERT: {med['name']} contains "
                        f"{info['allergy_flag']} which conflicts "
                        f"with your allergy profile"
                    )
            enriched.append({
                **med,
                "drug_class":   info["class"],
                "side_effects": info["side_effects"],
                "warnings":     info["warnings"],
                "interactions": info["interactions"],
            })
        else:
            enriched.append({
                **med,
                "drug_class":   "Unknown",
                "side_effects": ["Verify with your pharmacist"],
                "warnings":     ["Not found in local database"],
                "interactions": [],
            })

    # Cross-interaction check
    names_lower = [m["name"].lower() for m in medicines]
    for med in enriched:
        for interaction in med.get("interactions", []):
            inter_lower = interaction.lower()
            for other in names_lower:
                if (
                    other != med["name"].lower()
                    and (inter_lower in other or other in inter_lower)
                ):
                    pair = f"{med['name']} + {interaction}"
                    if pair not in cross_interactions:
                        cross_interactions.append(pair)

    overall_safety = (
        "dangerous" if allergy_alerts else
        "caution"   if cross_interactions else
        "safe"
    )

    return {
        "raw_text":           raw_text,
        "medicines":          enriched,
        "medicines_count":    len(enriched),
        "allergy_alerts":     allergy_alerts,
        "interactions":       cross_interactions,
        "side_effects":       [],
        "condition_warnings": [],
        "overall_safety":     overall_safety,
        "safety_advice": (
            "Allergy conflict — do not take without doctor approval"
            if allergy_alerts else
            "Drug interaction detected — consult your pharmacist"
            if cross_interactions else
            "No major issues found in our database"
        ),
        "confidence": "high" if len(raw_text) > 30 else "low",
        "disclaimer": (
            "Always verify with your pharmacist "
            "before taking any medication."
        ),
    }
