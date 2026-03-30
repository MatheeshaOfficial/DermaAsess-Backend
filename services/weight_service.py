# services/weight_service.py
# Uses nateraw/food from Hugging Face
# 89% accuracy on Food-101, Apache 2.0 license
# Zero training needed

import io
import torch
from PIL import Image
DEVICE = torch.device("cuda" if torch.cuda.is_available() else "cpu")


# ── Calorie database per 100g ─────────────────────────────────
FOOD_CALORIES = {
    "apple_pie": 237, "baby_back_ribs": 292, "baklava": 428,
    "beef_carpaccio": 135, "beef_tartare": 174, "beet_salad": 58,
    "beignets": 307, "bibimbap": 124, "bread_pudding": 198,
    "breakfast_burrito": 215, "bruschetta": 195, "caesar_salad": 110,
    "cannoli": 333, "caprese_salad": 145, "carrot_cake": 415,
    "ceviche": 80, "cheesecake": 321, "cheese_plate": 380,
    "chicken_curry": 165, "chicken_quesadilla": 223,
    "chicken_wings": 290, "chocolate_cake": 371,
    "chocolate_mousse": 214, "churros": 376, "clam_chowder": 102,
    "club_sandwich": 280, "crab_cakes": 162, "creme_brulee": 205,
    "croque_madame": 288, "cup_cakes": 375, "deviled_eggs": 144,
    "donuts": 452, "dumplings": 150, "edamame": 121,
    "eggs_benedict": 255, "escargots": 90, "falafel": 333,
    "filet_mignon": 227, "fish_and_chips": 262, "foie_gras": 462,
    "french_fries": 312, "french_onion_soup": 33,
    "french_toast": 229, "fried_calamari": 175, "fried_rice": 163,
    "frozen_yogurt": 97, "garlic_bread": 295, "gnocchi": 132,
    "greek_salad": 64, "grilled_cheese_sandwich": 290,
    "grilled_salmon": 208, "guacamole": 149, "gyoza": 195,
    "hamburger": 295, "hot_and_sour_soup": 35, "hot_dog": 242,
    "huevos_rancheros": 183, "hummus": 177, "ice_cream": 207,
    "lasagna": 135, "lobster_bisque": 96,
    "lobster_roll_sandwich": 245, "macaroni_and_cheese": 164,
    "macarons": 404, "miso_soup": 40, "mussels": 86, "nachos": 306,
    "omelette": 149, "onion_rings": 411, "oysters": 68,
    "pad_thai": 160, "paella": 189, "pancakes": 227,
    "panna_cotta": 128, "peking_duck": 337, "pho": 65,
    "pizza": 266, "pork_chop": 231, "poutine": 230,
    "prime_rib": 291, "pulled_pork_sandwich": 290, "ramen": 436,
    "ravioli": 218, "red_velvet_cake": 369, "risotto": 166,
    "samosa": 262, "sashimi": 127, "scallops": 111,
    "seaweed_salad": 45, "shrimp_and_grits": 180,
    "spaghetti_bolognese": 131, "spaghetti_carbonara": 198,
    "spring_rolls": 161, "steak": 252,
    "strawberry_shortcake": 259, "sushi": 143, "tacos": 219,
    "takoyaki": 200, "tiramisu": 240, "tuna_tartare": 108,
    "waffles": 310,
}

# Typical serving sizes in grams
SERVING_SIZES = {
    "soup": 250, "salad": 150, "pizza": 150,
    "burger": 200, "hamburger": 200, "sandwich": 180,
    "cake": 100, "ice_cream": 100, "sushi": 180,
    "ramen": 400, "pho": 400, "default": 200,
}

# Macro estimates per 100g by food type
MACROS = {
    "high_protein": {"protein": 25, "carbs":  5, "fat": 10},
    "high_carb":    {"protein":  5, "carbs": 50, "fat":  3},
    "balanced":     {"protein": 12, "carbs": 25, "fat": 10},
    "high_fat":     {"protein":  8, "carbs": 10, "fat": 25},
    "vegetable":    {"protein":  3, "carbs": 10, "fat":  1},
}

FOOD_TYPE_MAP = {
    "steak": "high_protein", "salmon": "high_protein",
    "chicken": "high_protein", "egg": "high_protein",
    "sushi": "high_protein", "sashimi": "high_protein",
    "tuna": "high_protein", "scallops": "high_protein",
    "rice": "high_carb", "pasta": "high_carb",
    "pizza": "high_carb", "bread": "high_carb",
    "pancakes": "high_carb", "waffles": "high_carb",
    "ramen": "high_carb", "pho": "high_carb",
    "salad": "vegetable", "seaweed": "vegetable",
    "edamame": "vegetable", "beet": "vegetable",
    "donuts": "high_fat", "fries": "high_fat",
    "cheese": "high_fat", "ice_cream": "high_fat",
    "baklava": "high_fat", "foie_gras": "high_fat",
}

HEALTH_SCORES = {
    "seaweed_salad": 10, "edamame": 9, "sashimi": 9,
    "greek_salad": 9, "caprese_salad": 8, "beet_salad": 9,
    "grilled_salmon": 8, "ceviche": 8, "miso_soup": 7,
    "hummus": 7, "omelette": 7, "steak": 6,
    "spaghetti_bolognese": 5, "pizza": 5, "hamburger": 5,
    "hamburger": 4, "french_fries": 3, "donuts": 2,
    "hot_dog": 3, "nachos": 3, "poutine": 3,
    "ice_cream": 4, "cup_cakes": 3, "chocolate_cake": 3,
}


def load_food_model():
    """Load nateraw/food from Hugging Face."""
    from transformers import (
        AutoModelForImageClassification,
        AutoImageProcessor
    )
    print("Loading food classifier from Hugging Face...")
    processor = AutoImageProcessor.from_pretrained("nateraw/food")
    # Low memory usage and half-precision floats to fit tight limits
    model = AutoModelForImageClassification.from_pretrained(
        "nateraw/food",
        torch_dtype=torch.float16,
        low_cpu_mem_usage=True
    ).to(DEVICE)
    model.eval()
    
    # Get label list from model config
    labels = model.config.id2label
    print(f"Food model loaded! Classes: {len(labels)}")
    return model, processor, labels


def get_serving_size(food_name: str) -> int:
    for key, size in SERVING_SIZES.items():
        if key in food_name:
            return size
    return SERVING_SIZES["default"]


def get_macro_type(food_name: str) -> str:
    for key, ftype in FOOD_TYPE_MAP.items():
        if key in food_name:
            return ftype
    return "balanced"


def generate_advice(
    food_name: str,
    calories: int,
    user_weight: float = None,
    goal_weight: float = None
) -> str:
    parts = []

    if calories > 600:
        parts.append(
            f"This is a high-calorie meal (~{calories} kcal). "
            "Consider a lighter dinner to balance your day."
        )
    elif calories < 200:
        parts.append(
            f"Light meal (~{calories} kcal). "
            "Make sure you are eating enough throughout the day."
        )
    else:
        parts.append(f"Moderate meal (~{calories} kcal).")

    macro_type = get_macro_type(food_name)
    if macro_type == "high_protein":
        parts.append(
            "Good protein content — supports muscle and keeps you full."
        )
    elif macro_type == "high_carb":
        parts.append(
            "High in carbs — best consumed earlier in the day for energy."
        )
    elif macro_type == "high_fat":
        parts.append("Higher in fat — enjoy in moderation.")
    elif macro_type == "vegetable":
        parts.append(
            "Excellent choice — high in fiber and nutrients."
        )

    if user_weight and goal_weight:
        diff = user_weight - goal_weight
        if diff > 5:
            parts.append(
                f"You are {diff:.1f}kg above your goal. "
                "Aim for a 300-500 kcal daily deficit."
            )
        elif diff < -2:
            parts.append(
                "You are below your goal weight. "
                "Focus on nutrient-dense foods."
            )
        else:
            parts.append(
                "You are close to your goal weight. Keep it up!"
            )

    return " ".join(parts)


def analyze_meal(
    image_bytes: bytes,
    *args,
    **kwargs
) -> dict:
    """Classify food and return calories + macros + advice."""
    model, processor, labels = load_food_model()

    # Backwards compatibility handler since signature was modified to ignore mime_type
    user_weight_kg = kwargs.get("user_weight_kg")
    goal_weight_kg = kwargs.get("goal_weight_kg")
    if args:
        # if router sends mime_type as first positional arg
        if len(args) > 0 and isinstance(args[0], (int, float)):
            user_weight_kg = args[0]
        if len(args) > 1 and isinstance(args[1], (int, float)):
            goal_weight_kg = args[1]

    img    = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    inputs = processor(images=img, return_tensors="pt").to(DEVICE)

    with torch.no_grad():
        outputs = model(**inputs)
        probs   = torch.softmax(outputs.logits, dim=1)[0]

    top3_idx   = probs.topk(3).indices.tolist()
    top3_probs = probs.topk(3).values.tolist()

    top_food   = labels[top3_idx[0]]           # e.g. "french_fries"
    confidence = top3_probs[0]

    # Calories
    cal_per_100g  = FOOD_CALORIES.get(top_food, 200)
    serving_g     = get_serving_size(top_food)
    total_calories = int(cal_per_100g * serving_g / 100)

    # Macros
    macro_type    = get_macro_type(top_food)
    macro_per_100 = MACROS.get(macro_type, MACROS["balanced"])
    macros = {
        "protein_g": round(macro_per_100["protein"] * serving_g / 100, 1),
        "carbs_g":   round(macro_per_100["carbs"]   * serving_g / 100, 1),
        "fat_g":     round(macro_per_100["fat"]      * serving_g / 100, 1),
    }

    # Food items display names
    food_items = [
        labels[i].replace("_", " ").title()
        for i in top3_idx
    ]

    # Health score
    health_score = HEALTH_SCORES.get(top_food, 5)

    # Advice
    advice = generate_advice(
        top_food, total_calories,
        user_weight_kg, goal_weight_kg
    )

    res = {
        "food_items":          food_items,
        "top_food":            top_food.replace("_", " ").title(),
        "estimated_calories":  total_calories,
        "calories_estimate":   total_calories, # legacy compatibility
        "macros":              macros,
        "protein_g":           macros["protein_g"], # legacy compatibility
        "carbs_g":             macros["carbs_g"], # legacy compatibility
        "fat_g":               macros["fat_g"], # legacy compatibility
        "health_score":        health_score,
        "confidence":          round(confidence * 100, 1),
        "advice":              advice,
        "serving_size_g":      serving_g,
        "calories_per_100g":   cal_per_100g,
        "alternatives": [
            "Try a side salad to add fiber and nutrients",
            "Choose grilled over fried when possible",
            "Add more vegetables to increase nutrient density",
        ],
    }

    # Memory Cleanup
    del model
    del processor
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
    import gc
    gc.collect()

    return res
