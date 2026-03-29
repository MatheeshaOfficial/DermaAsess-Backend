# services/medisafe_service.py
# Uses chinmays18/medical-prescription-ocr from Hugging Face
# No training needed, no large files to store

import io
import re
import pickle
import torch
from PIL import Image, ImageEnhance
from transformers import DonutProcessor, VisionEncoderDecoderModel

DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")

# ── Singletons ────────────────────────────────────────────────
_processor = None
_model     = None

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
        "warnings":    ["Do not exceed 4g per day", "Avoid alcohol"],
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
        "interactions":  ["Simvastatin", "Cyclosporine"],
        "allergy_flag":  None,
    },
    "aspirin": {
        "class":        "NSAID Antiplatelet",
        "side_effects": ["Stomach bleeding", "Increased bleeding risk"],
        "warnings":     ["Never give to children under 16", "Take with food"],
        "interactions":  ["Warfarin", "Ibuprofen"],
        "allergy_flag":  "aspirin",
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
}

ALIASES = {
    "tylenol":        "paracetamol",
    "panadol":        "paracetamol",
    "acetaminophen":  "paracetamol",
    "advil":          "ibuprofen",
    "nurofen":        "ibuprofen",
    "augmentin":      "amoxicillin",
    "zithromax":      "azithromycin",
    "azithral":       "azithromycin",
    "cifran":         "ciprofloxacin",
    "ciplox":         "ciprofloxacin",
    "lipitor":        "atorvastatin",
    "glucophage":     "metformin",
    "prilosec":       "omeprazole",
    "losec":          "omeprazole",
    "norvasc":        "amlodipine",
    "ventolin":       "salbutamol",
    "brufen":         "ibuprofen",
    "calpol":         "paracetamol",
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


def load_ocr_model():
    """Load chinmays18/medical-prescription-ocr from Hugging Face."""
    global _processor, _model
    if _model is None:
        print("Loading prescription OCR model from Hugging Face...")
        _processor = DonutProcessor.from_pretrained(
            "chinmays18/medical-prescription-ocr"
        )
        _model = VisionEncoderDecoderModel.from_pretrained(
            "chinmays18/medical-prescription-ocr"
        ).to(DEVICE)
        _model.eval()
        print("Prescription OCR model loaded!")
    return _processor, _model


def enhance_image(img: Image.Image) -> Image.Image:
    """Enhance prescription image for better OCR."""
    w, h = img.size
    if w < 800:
        scale = 800 / w
        img   = img.resize(
            (int(w * scale), int(h * scale)),
            Image.LANCZOS
        )
    img = ImageEnhance.Contrast(img).enhance(1.8)
    img = ImageEnhance.Sharpness(img).enhance(2.0)
    return img


def run_ocr(image_bytes: bytes) -> str:
    """
    Run Donut-based OCR on prescription image.
    Returns extracted text string.
    """
    processor, model = load_ocr_model()

    img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    img = enhance_image(img)

    pixel_values = processor(
        images=img, return_tensors="pt"
    ).pixel_values.to(DEVICE)

    task_prompt      = "<s_ocr>"
    decoder_input_ids = processor.tokenizer(
        task_prompt,
        add_special_tokens=False,
        return_tensors="pt"
    ).input_ids.to(DEVICE)

    with torch.no_grad():
        outputs = model.generate(
            pixel_values,
            decoder_input_ids=decoder_input_ids,
            max_length=model.decoder.config.max_position_embeddings,
            early_stopping=True,
            pad_token_id=processor.tokenizer.pad_token_id,
            eos_token_id=processor.tokenizer.eos_token_id,
            use_cache=True,
            num_beams=1,
            bad_words_ids=[[processor.tokenizer.unk_token_id]],
            return_dict_in_generate=True,
        )

    sequence = processor.batch_decode(
        outputs.sequences
    )[0]
    sequence = sequence.replace(
        processor.tokenizer.eos_token, ""
    ).replace(
        processor.tokenizer.pad_token, ""
    )
    # Remove task prompt token
    sequence = re.sub(r"<.*?>", "", sequence).strip()
    return sequence


def parse_medicines(raw_text: str) -> list:
    """Extract medicine names, dosages, frequency from OCR text."""
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

        key = name.lower()
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
    """Look up medicine in local database."""
    key = name.lower().strip()
    if key in DRUG_DB:
        return DRUG_DB[key]
    if key in ALIASES:
        return DRUG_DB.get(ALIASES[key])
    for db_key in DRUG_DB:
        if db_key in key or key in db_key:
            return DRUG_DB[db_key]
    return None


def analyze_prescription(
    image_bytes: bytes,
    *args,
    **kwargs
) -> dict:
    """Full prescription analysis pipeline."""
    # Handle user_allergies whether passed as arg 2 or kwarg
    user_allergies = kwargs.get("user_allergies", [])
    if not user_allergies and args and isinstance(args[0], list):
        user_allergies = args[0]
        
    user_allergies_lower = [a.lower() for a in user_allergies]

    # Step 1 — OCR
    raw_text = run_ocr(image_bytes)

    # Step 2 — Parse medicines
    medicines = parse_medicines(raw_text)

    # Step 3 — Enrich with drug database
    enriched           = []
    allergy_alerts     = []
    cross_interactions = []

    for med in medicines:
        info = lookup_medicine(med["name"])
        if info:
            # Check allergy
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

    # Step 4 — Cross interaction check
    names_lower = [m["name"].lower() for m in medicines]
    for med in enriched:
        for interaction in med.get("interactions", []):
            interaction_lower = interaction.lower()
            for other_name in names_lower:
                if (
                    other_name != med["name"].lower()
                    and (
                        interaction_lower in other_name
                        or other_name in interaction_lower
                    )
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
        "raw_text":        raw_text,
        "medicines":       enriched,
        "medicines_count": len(enriched),
        "allergy_alerts":  allergy_alerts,
        "interactions":    cross_interactions,
        "side_effects":    [],
        "condition_warnings": [],
        "overall_safety":  overall_safety,
        "safety_advice": (
            "Allergy conflict detected — do not take without doctor approval"
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
