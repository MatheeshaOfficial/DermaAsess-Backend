import io
import re
import torch
import timm
import numpy as np
import albumentations as A
from albumentations.pytorch import ToTensorV2
from PIL import Image

DEVICE   = torch.device("cuda" if torch.cuda.is_available() else "cpu")
IMG_SIZE = 224

val_transform = A.Compose([
    A.Resize(IMG_SIZE, IMG_SIZE),
    A.Normalize(
        mean=[0.485, 0.456, 0.406],
        std =[0.229, 0.224, 0.225]
    ),
    ToTensorV2(),
])

_model       = None
_checkpoint  = None

def clean_label(label: str) -> str:
    # Removes e.g. "9. " at start and "- 1.7k" at end
    return re.sub(r'^\d+\.\s*|-\s*[\d.]+[kKmMgG]?$', '', label).strip()


def load_model():
    global _model, _checkpoint
    if _model is None:
        print("Loading skin disease model...")
        _checkpoint = torch.load(
            "./models/skin_model.pth",
            map_location=DEVICE
        )
        _model = timm.create_model(
            _checkpoint["model_arch"],
            pretrained=False,
            num_classes=_checkpoint["num_classes"]
        )
        _model.load_state_dict(_checkpoint["model_state"])
        _model.eval()
        _model.to(DEVICE)
        print(
            f"Model loaded! "
            f"Classes: {_checkpoint['num_classes']} | "
            f"Val acc: {_checkpoint['val_acc']:.2f}%"
        )
    return _model, _checkpoint


def predict_skin(image_bytes: bytes) -> dict:
    model, ckpt = load_model()

    label_names  = ckpt["label_names"]   # {0: "Acne", 1: "Athlete-foot", ...}
    severity_map = ckpt["severity_map"]  # from training

    # Preprocess
    image  = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    image  = np.array(image)
    tensor = val_transform(
        image=image
    )["image"].unsqueeze(0).to(DEVICE)

    # Inference
    with torch.no_grad():
        logits = model(tensor)
        probs  = torch.softmax(logits, dim=1)[0]

    pred_idx   = probs.argmax().item()
    confidence = probs[pred_idx].item()
    raw_pred_name = label_names[pred_idx]
    pred_name  = clean_label(raw_pred_name)
    severity   = severity_map.get(raw_pred_name, {
        "severity": 3,
        "action":   "clinic",
        "risk":     "low",
        "advice":   "Please consult a dermatologist for proper diagnosis."
    })

    # Top 3 predictions
    top3_idx   = probs.topk(3).indices.tolist()
    top3_probs = probs.topk(3).values.tolist()
    possible_conditions = [
        clean_label(label_names[i]) for i in top3_idx
    ]

    # Warning signs for medium/high severity
    warning_signs = []
    if severity["severity"] >= 5:
        warning_signs = [
            "Spreading to other areas of the body",
            "Increasing pain or discomfort",
            "Fever or swollen lymph nodes nearby",
            "No improvement after 48 hours",
        ]
    elif severity["severity"] >= 3:
        warning_signs = [
            "Condition worsens over 3-5 days",
            "Spreads to new areas",
            "Signs of infection: warmth, pus, red streaks",
        ]

    return {
        "severity_score":      severity["severity"],
        "contagion_risk":      severity["risk"],
        "recommended_action":  severity["action"],
        "possible_conditions": possible_conditions,
        "ai_diagnosis": (
            f"The model identified this as likely {pred_name} "
            f"with {round(confidence * 100, 1)}% confidence."
        ),
        "ai_advice":     severity["advice"],
        "warning_signs": warning_signs,
        "confidence":    round(confidence * 100, 1),
        "disclaimer": (
            "This is AI-based guidance only, not a medical diagnosis. "
            "Always consult a qualified dermatologist."
        ),
    }
