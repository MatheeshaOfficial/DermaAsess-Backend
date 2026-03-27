import httpx
from config import USDA_API_KEY


USDA_API_KEY = USDA_API_KEY

async def lookup_nutrition(food_name: str) -> dict:
    if not USDA_API_KEY:
        return {}
    
    url = "https://api.nal.usda.gov/fdc/v1/foods/search"
    params = {
        "api_key": USDA_API_KEY,
        "query": food_name,
        "pageSize": 1
    }
    
    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data.get("foods"):
                food = data["foods"][0]
                macros = {"calories": 0, "protein": 0, "carbs": 0, "fat": 0}
                for nutrient in food.get("foodNutrients", []):
                    name = nutrient.get("nutrientName", "").lower()
                    val = nutrient.get("value", 0)
                    if "energy" in name: macros["calories"] = val
                    elif "protein" in name: macros["protein"] = val
                    elif "carbohydrate" in name: macros["carbs"] = val
                    elif "lipid" in name: macros["fat"] = val
                return macros
        except Exception:
            pass
    return {}
