import json
import google.generativeai as genai
from typing import List, Optional, Dict
from config import GEMINI_API_KEY


genai.configure(api_key=GEMINI_API_KEY)
model = genai.GenerativeModel('gemini-1.5-flash')

def clean_json_response(text: str) -> str:
    text = text.strip()
    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[len("```"):].strip()
    if text.endswith("```"):
        text = text[:-len("```")].strip()
    return text

async def analyze_skin_image(image_bytes: bytes, mime_type: str, symptoms: str, profile: dict) -> dict:
    prompt = f"""
    You are an expert dermatologist AI. Analyze the provided skin image and symptoms: '{symptoms}'.
    Profile info: Age {profile.get('age', 'Unknown')}, Allergies: {profile.get('allergies', 'None')}, Conditions: {profile.get('conditions', 'None')}.
    
    Respond STRICTLY in JSON format:
    {{
        "severity": integer (1-10),
        "contagion_risk": string ("low", "medium", "high"),
        "recommended_action": string ("self-care", "clinic", "emergency"),
        "diagnosis": string (description of findings),
        "possible_conditions": [string],
        "advice": string (what to do next)
    }}
    """
    vision_model = genai.GenerativeModel('gemini-1.5-flash')
    response = vision_model.generate_content([
        {"mime_type": mime_type, "data": image_bytes},
        prompt
    ])
    try:
        data = clean_json_response(response.text)
        return json.loads(data)
    except Exception:
        return {"severity": 5, "contagion_risk": "low", "recommended_action": "clinic", "diagnosis": "Could not parse diagnosis.", "possible_conditions": ["Unknown"], "advice": "Please consult a doctor."}

async def ocr_prescription(image_bytes: bytes, mime_type: str) -> dict:
    prompt = """
    Extract all medicines from this prescription/label.
    Respond STRICTLY in JSON format:
    {
        "medicines": [
            {
                "name": string,
                "dosage": string,
                "frequency": string
            }
        ]
    }
    """
    response = model.generate_content([{"mime_type": mime_type, "data": image_bytes}, prompt])
    try:
        data = clean_json_response(response.text)
        return json.loads(data)
    except Exception:
         return {"medicines": []}

async def check_drug_safety(medicines: List[Dict], profile: dict) -> dict:
    prompt = f"""
    Check safety for the following medicines: {json.dumps(medicines)}.
    User Profile: Age {profile.get('age', 'Unknown')}, Allergies: {profile.get('allergies', 'None')}, Conditions: {profile.get('conditions', 'None')}.
    
    Respond STRICTLY in JSON format:
    {{
        "overall_safety": string ("safe", "caution", "dangerous"),
        "advice": string,
        "interactions": [string],
        "allergy_alerts": [string]
    }}
    """
    response = model.generate_content([prompt])
    try:
        data = clean_json_response(response.text)
        return json.loads(data)
    except Exception:
        return {"overall_safety": "caution", "advice": "Please consult your pharmacist.", "interactions": [], "allergy_alerts": []}

async def analyze_meal(image_bytes: bytes, mime_type: str) -> dict:
    prompt = """
    Analyze this meal photo. Provide food items and estimate calories.
    Respond STRICTLY in JSON format:
    {
        "food_items": [string],
        "calories_estimate": integer,
        "protein_g": integer,
        "carbs_g": integer,
        "fat_g": integer,
        "advice": string
    }
    """
    response = model.generate_content([{"mime_type": mime_type, "data": image_bytes}, prompt])
    try:
        data = clean_json_response(response.text)
        return json.loads(data)
    except Exception:
        return {"food_items": ["Unknown"], "calories_estimate": 0, "protein_g": 0, "carbs_g": 0, "fat_g": 0, "advice": "Could not analyze meal."}

async def chat_with_dermabot(message: str, image_bytes: Optional[bytes], mime_type: Optional[str], history: List[dict], profile: dict, rag_context: str = "") -> str:
    chat = model.start_chat()
    system_prompt = f"You are DermaBot, a helpful health assistant. User Profile: Age {profile.get('age','Unk')}, Allergies: {profile.get('allergies','None')}, Conditions: {profile.get('conditions','None')}."
    try:
        if image_bytes and mime_type:
            response = chat.send_message([{"mime_type": mime_type, "data": image_bytes}, system_prompt + message])
        else:
            hist_str = json.dumps(history[-10:])
            response = chat.send_message(system_prompt + "\nHistory: " + hist_str + "\nUser: " + message)
        return response.text
    except Exception as e:
        return f"Sorry, I encountered an error: {str(e)}"
