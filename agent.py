from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
import os
import sqlite3
from sentence_transformers import SentenceTransformer
import faiss;
import numpy as np;
import openai
import random
from typing import Optional, Dict, List, Any
import json
import re

load_dotenv()

def expand_structured_meal(item_info, restaurant):
    """Automatically add sides and sauces when an item comes from a structured meal section.
    
    Parameters
    ----------
    item_info : tuple
        (name, restaurant, section, calories, protein, fat, carbs, sodium, fiber, sugar, calcium, iron, potassium)
    restaurant : str
        Restaurant name
        
    Returns
    -------
    list
        List of item tuples including the main item plus any required sides/sauces
    """
    name, rest, section, calories, protein, fat, carbs, sodium, fiber, sugar, calcium, iron, potassium = item_info
    section_lower = section.lower()
    
    # Check if this is a component that requires a base meal (reverse dependency)
    is_component_needing_base = any(phrase in section_lower for phrase in [
        'choose protein', 'choose sauce', 'choose sides', 'choose topping',
        'choose one protein', 'choose up to five vegetables', 'choose up to two sauces',
        'toppings and sauce', 'toppings and sauces',
        'build your own pasta protein', 'build your own pasta toppings', 
        'build your own pizza (toppings)', 'build your own pizza (sauce',
        'build your own burger (choose', 'build a biscuit or sandwich fillings',
        'choose your toppings)', 'choose your ingredients)'
    ])
    
    # Check if this item comes from a structured meal section (forward dependency)
    requires_sides = any(phrase in section_lower for phrase in [
        'choice of', 'choose', 'sides', 'sauce', 'toppings'
    ]) and not is_component_needing_base
    
    if not requires_sides and not is_component_needing_base:
        return [item_info]  # Return just the original item
    
    conn = sqlite3.connect("duke_nutrition.db")
    cursor = conn.cursor()
    
    expanded_items = [item_info]  # Start with the selected item
    
    # Handle reverse dependency: component needs a base meal
    if is_component_needing_base:
        # Find the base meal section for this restaurant
        cursor.execute(
            """
            SELECT name, restaurant, section, calories, protein, total_fat, total_carbs,
                   sodium, dietary_fiber, total_sugars, calcium, iron, potassium
            FROM items 
            WHERE restaurant = ? AND (
                section LIKE '%build your own%' OR 
                section LIKE '%choose one%' OR
                section LIKE '%base%' OR
                section LIKE '%choose one base%' OR
                section LIKE '%base (choose one)%' OR
                section LIKE '%crust - choose one%' OR
                section LIKE '%breads (choose%' OR
                section LIKE '%wrap%base%' OR
                section LIKE '%burrito%base%'
            )
            AND calories IS NOT NULL
            ORDER BY calories
            """, 
            (restaurant,)
        )
        
        available_bases = [item for item in cursor.fetchall() if validate_nutrition_data(item)]
        
        if available_bases:
            # Select an appropriate base - prioritize items that look like actual bases
            # (higher calories, moderate to high carbs, not sauces/toppings)
            base_item = None
            
            # First, try to find pasta, rice, tortilla, bread bases (high carb, substantial calories)
            for item in available_bases:
                name_lower = item[0].lower()
                section_lower_base = item[2].lower()
                calories = item[3]
                carbs = item[6]
                
                # Context-aware base selection
                is_good_base = False
                
                # If we're building pasta (protein is from pasta section), prefer pasta bases
                if 'pasta' in section_lower:
                    is_good_base = (any(pasta in name_lower for pasta in ['pasta', 'spaghetti', 'fettuccine', 'rigatoni', 'penne']) 
                                   and 'pasta' in section_lower_base and calories >= 200 and carbs >= 50)
                
                # If we're building pizza, prefer pizza crusts  
                elif 'pizza' in section_lower:
                    is_good_base = ('crust' in name_lower or 'dough' in name_lower) and 'pizza' in section_lower_base
                
                # If we're building rice bowls, prefer rice
                elif 'rice' in section_lower or 'bowl' in section_lower:
                    is_good_base = 'rice' in name_lower and calories >= 100 and carbs >= 30
                
                # If we're building burritos/tacos, prefer tortillas
                elif any(wrap in section_lower for wrap in ['burrito', 'tortilla', 'taco', 'wrap']):
                    is_good_base = 'tortilla' in name_lower and calories >= 100
                
                # If we're building sandwiches, prefer bread
                elif any(bread in section_lower for bread in ['sandwich', 'bread', 'biscuit']):
                    is_good_base = any(bread in name_lower for bread in ['bread', 'biscuit']) and calories >= 100
                
                # General fallback: substantial base foods
                else:
                    is_good_base = (any(base_food in name_lower for base_food in ['pasta', 'rice', 'tortilla', 'bread', 'crust', 'noodle']) 
                                   and calories >= 200 and carbs >= 30)
                
                if is_good_base:
                    base_item = item
                    break
            
            # If no clear base found, fall back to highest calorie valid option
            if not base_item and available_bases:
                base_item = max(available_bases, key=lambda x: x[3])  # Highest calories
                
            if base_item:
                expanded_items.insert(0, base_item)  # Put base first
            
            # Add complementary components to make a complete meal
            if ('choose protein' in section_lower or 'choose one protein' in section_lower or 
                'build your own pasta protein' in section_lower or 'build your own pizza' in section_lower):
                # If we selected a protein, add some basic toppings/vegetables
                cursor.execute(
                    """
                    SELECT name, restaurant, section, calories, protein, total_fat, total_carbs,
                           sodium, dietary_fiber, total_sugars, calcium, iron, potassium
                    FROM items 
                    WHERE restaurant = ? AND (
                        CASE 
                            WHEN ? LIKE '%pasta%' THEN section LIKE '%build your own pasta toppings%'
                            WHEN ? LIKE '%pizza%' THEN section LIKE '%build your own pizza (toppings)%'
                            ELSE (
                                section LIKE '%choose topping%' OR
                                section LIKE '%choose up to five vegetables%' OR
                                section LIKE '%vegetables%'
                            )
                        END
                    )
                    AND calories IS NOT NULL
                    ORDER BY calories
                    LIMIT 3
                    """, 
                    (restaurant, section_lower, section_lower)
                )
                
                toppings = [item for item in cursor.fetchall() if validate_nutrition_data(item)]
                expanded_items.extend(toppings[:3])  # Add up to 3 vegetables/toppings
                
                # Add a sauce
                cursor.execute(
                    """
                    SELECT name, restaurant, section, calories, protein, total_fat, total_carbs,
                           sodium, dietary_fiber, total_sugars, calcium, iron, potassium
                    FROM items 
                    WHERE restaurant = ? AND (
                        CASE 
                            WHEN ? LIKE '%pasta%' THEN section LIKE '%build your own pasta%sauce%'
                            WHEN ? LIKE '%pizza%' THEN section LIKE '%build your own pizza%sauce%'
                            ELSE (
                                section LIKE '%choose sauce%' OR
                                section LIKE '%choose up to two sauces%' OR
                                section LIKE '%sauces%'
                            )
                        END
                    )
                    AND calories IS NOT NULL
                    ORDER BY calories
                    LIMIT 1
                    """, 
                    (restaurant, section_lower, section_lower)
                )
                
                sauces = [item for item in cursor.fetchall() if validate_nutrition_data(item)]
                if sauces:
                    expanded_items.append(sauces[0])
    
    # Handle forward dependency: main item requires sides/sauces  
    else:
        # Determine how many sides and sauces to add based on section text
        num_sides = 0
        num_sauces = 0
        
        if 'two sides' in section_lower or '2 sides' in section_lower:
            num_sides = 2
        elif 'side' in section_lower:
            num_sides = 1
            
        if 'sauce' in section_lower:
            num_sauces = 1
        
        # Find appropriate sides for this restaurant
        if num_sides > 0:
            # Look for side sections at this restaurant
            cursor.execute(
                """
                SELECT name, restaurant, section, calories, protein, total_fat, total_carbs,
                       sodium, dietary_fiber, total_sugars, calcium, iron, potassium
                FROM items 
                WHERE restaurant = ? AND (
                    section LIKE '%Side%' OR 
                    section = 'A La Carte' OR
                    section LIKE '%Sides%'
                )
                AND calories IS NOT NULL
                ORDER BY calories
                """, 
                (restaurant,)
            )
            
            available_sides = [item for item in cursor.fetchall() if validate_nutrition_data(item)]
            
            if available_sides:
                # Select sides that complement the meal nutritionally
                selected_sides = []
                used_sides = set()
                
                for i in range(min(num_sides, len(available_sides))):
                    # Find a side we haven't used yet
                    for side in available_sides:
                        if side[0] not in used_sides:  # side[0] is the name
                            selected_sides.append(side)
                            used_sides.add(side[0])
                            break
                    
                    # If we've used all sides, allow repeats but start from different ones
                    if len(selected_sides) <= i:
                        side = available_sides[i % len(available_sides)]
                        selected_sides.append(side)
                        
                expanded_items.extend(selected_sides)
        
        # Find appropriate sauces
        if num_sauces > 0:
            cursor.execute(
                """
                SELECT name, restaurant, section, calories, protein, total_fat, total_carbs,
                       sodium, dietary_fiber, total_sugars, calcium, iron, potassium
                FROM items 
                WHERE restaurant = ? AND (
                    section LIKE '%Sauce%' OR 
                    section LIKE '%Dressing%'
                )
                AND calories IS NOT NULL
                ORDER BY calories
                """, 
                (restaurant,)
            )
            
            available_sauces = [item for item in cursor.fetchall() if validate_nutrition_data(item)]
            
            if available_sauces:
                # Select a complementary sauce (prefer lower calories)
                sauce = available_sauces[0]
                expanded_items.append(sauce)
    
    conn.close()
    return expanded_items

def validate_nutrition_data(item_data) -> bool:
    """Validate that nutrition data is reasonable and not corrupted.
    
    Parameters
    ----------
    item_data : tuple or dict
        Food item data containing nutrition information
        
    Returns
    -------
    bool
        True if nutrition data appears reasonable, False if likely corrupted
    """
    # Extract nutrition values - handle both tuple and dict formats
    if isinstance(item_data, (tuple, list)):
        # Assuming format: (name, restaurant, section, calories, protein, fat, carbs, sodium, fiber, sugar, ...)
        if len(item_data) < 7:
            return False
        name = item_data[0] if len(item_data) > 0 else ""
        section = item_data[2] if len(item_data) > 2 else ""
        calories = item_data[3] if len(item_data) > 3 else 0
        protein = item_data[4] if len(item_data) > 4 else 0  
        fat = item_data[5] if len(item_data) > 5 else 0
        carbs = item_data[6] if len(item_data) > 6 else 0
        sodium = item_data[7] if len(item_data) > 7 else 0
    elif isinstance(item_data, dict):
        name = item_data.get('name', item_data.get('food', ''))
        section = item_data.get('section', '')
        calories = item_data.get('calories', 0)
        protein = item_data.get('protein', 0)
        fat = item_data.get('fat', item_data.get('total_fat', 0))
        carbs = item_data.get('carbs', item_data.get('total_carbs', 0))
        sodium = item_data.get('sodium', 0)
    else:
        return False
    
    # Handle None values and convert to numeric types
    name = name or ""
    section = section or ""
    
    # Convert all nutrition values to float, handling None and string values
    try:
        calories = float(calories) if calories is not None else 0.0
    except (ValueError, TypeError):
        calories = 0.0
        
    try:
        protein = float(protein) if protein is not None else 0.0
    except (ValueError, TypeError):
        protein = 0.0
        
    try:
        fat = float(fat) if fat is not None else 0.0
    except (ValueError, TypeError):
        fat = 0.0
        
    try:
        carbs = float(carbs) if carbs is not None else 0.0
    except (ValueError, TypeError):
        carbs = 0.0
        
    try:
        sodium = float(sodium) if sodium is not None else 0.0
    except (ValueError, TypeError):
        sodium = 0.0
    
    # Determine if this is a combo/platter/full meal vs single component
    name_lower = name.lower()
    section_lower = section.lower()
    
    is_combo_meal = any(keyword in name_lower for keyword in [
        'combo', 'platter', 'plate', 'meal', 'bowl', 'entree', 'special',
        'dinner', 'lunch', 'breakfast', 'feast', 'sampler', 'loaded',
        'personal', 'artisan', 'wings', 'waffles', 'and'  # "chicken and waffles"
    ])
    
    is_multi_component = any(keyword in section_lower for keyword in [
        'combo', 'platter', 'choose', 'sides', 'with', 'toppings',
        'build your own', 'complete meal', 'personal', 'artisan',
        'entrees', 'small plates'  # wings are often in "small plates" but are full orders
    ])
    
    # Also check for pizza-specific cases (personal pizzas are full meals)
    is_full_pizza = 'pizza' in name_lower and ('personal' in section_lower or 'artisan' in section_lower)
    
    # Check for full protein orders (wings, large portions)
    is_protein_platter = any(keyword in name_lower for keyword in [
        'wings', 'ribs', 'brisket', 'pulled pork', 'full', 'large'
    ]) or 'small plates' in section_lower
    
    # Set validation limits based on meal type
    if is_combo_meal or is_multi_component or is_full_pizza or is_protein_platter:
        # More lenient limits for combo meals and multi-component items
        max_protein = 150  # A combo could reasonably have 150g protein
        max_fat = 120     # Full meals can be quite fatty
        max_carbs = 300   # Large meals with sides can have lots of carbs
        max_calories = 2500  # Full combo meals can be very high calorie
    else:
        # More realistic limits for single restaurant items
        max_protein = 100  # Increased from 80g - some protein dishes can be higher
        max_fat = 90      # Increased from 60g - salads, croissants, rich dishes
        max_carbs = 200   # Increased from 150g - drinks, pasta dishes, etc.
        max_calories = 2000
    
    # Apply validation ranges
    if not (0 <= protein <= max_protein):
        return False
    
    if not (0 <= fat <= max_fat):
        return False
        
    if not (0 <= carbs <= max_carbs):
        return False
    
    # Reasonable ranges for micronutrients (in mg) - adjusted for meal type
    if is_combo_meal or is_multi_component or is_full_pizza or is_protein_platter:
        max_sodium = 6000  # Full meals and pizzas can be very high in sodium
    else:
        max_sodium = 4000  # Single restaurant items can be quite salty
        
    if not (0 <= sodium <= max_sodium):
        return False
    
    # Calorie consistency check - macros should roughly match calories
    # Protein: 4 cal/g, Carbs: 4 cal/g, Fat: 9 cal/g
    calculated_calories = (protein * 4) + (carbs * 4) + (fat * 9)
    
    # Allow for some variance due to fiber, alcohol, and rounding
    if calories > 0 and calculated_calories > 0:
        ratio = calories / calculated_calories
        if not (0.4 <= ratio <= 2.5):  # More lenient for combo meals
            return False
    
    # Calories should be reasonable
    if not (0 <= calories <= max_calories):
        return False
    
    # Special case: desserts with extremely high protein are likely data errors
    is_dessert = any(keyword in name_lower for keyword in [
        'cake', 'cupcake', 'cookie', 'brownie', 'pie', 'tart', 
        'pudding', 'ice cream', 'gelato', 'donut', 'muffin'
    ])
    
    if is_dessert and protein > 50:  # Desserts shouldn't have extreme protein
        return False
    
    return True

OPENAI_API_BASE = os.getenv("OPENAI_API_BASE")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
openai.api_key = OPENAI_API_KEY

# If a custom OpenAI base URL is provided, configure the client to use it
if OPENAI_API_BASE:
    # Newer openai>=1.0 uses `base_url`; older (<1.0) uses `api_base`
    if hasattr(openai, "base_url"):
        openai.base_url = OPENAI_API_BASE
    else:
        openai.api_base = OPENAI_API_BASE
    os.environ.setdefault("OPENAI_BASE_URL", OPENAI_API_BASE)

agent = Agent(
    'openai:GPT 4.1',  
    deps_type=str,  
    system_prompt="""You are a diet and nutrition expert working with Duke Net Nutrition data.

Use ONLY foods contained in the database.

IMPORTANT: Nutrition data units in the database:
- Macronutrients (protein, total_fat, total_carbs, dietary_fiber, etc.) are measured in GRAMS
- Micronutrients (sodium, cholesterol, calcium, iron, potassium) are measured in MILLIGRAMS  
- Calories are measured in kcal
- The system automatically validates nutrition data to filter out unrealistic values (e.g., desserts with 600g protein)

CRITICAL: ALWAYS include protein information in your responses when discussing food items or meal plans. 
When mentioning any food item, include its protein content in grams (e.g., "Chicken Breast - 25g protein").
This is especially important for users focused on fitness, muscle building, or protein intake.

The database contains structured section information that categorizes foods by how they're meant to be combined:
- Base options (rice, noodles, greens)
- Protein choices 
- Vegetable selections (often "choose up to X")
- Sauces and toppings
- Build-your-own combinations for bowls, pizzas, pastas, etc.

For meal planning requests:
- For simple meal suggestions: use `create_meal` (returns 3-5 items)
- For build-your-own requests: use `build_custom_meal` (builds structured meals following restaurant sections)
- For comprehensive daily meal plans with specific calorie/protein targets: use `build_daily_meal_plan`

When the user requests a meal suggestion or plan, first call the `rank_foods` tool (if the *_rank columns are missing).

For comprehensive meal plans that specify nutritional targets (calories, protein, etc.), use `build_daily_meal_plan` 
which will intelligently select multiple items across different restaurants to meet the specified goals.

RESTAURANT DIVERSITY: When users ask for meals from "all different restaurants", "each restaurant", or similar 
language indicating they want maximum restaurant diversity, use `build_daily_meal_plan` with `max_items_per_restaurant=1`. 
This ensures each meal comes from a different restaurant. For normal requests, use the default value (3).

MEAL PLAN VARIETY: The meal planning algorithm includes randomization to provide different suggestions each time. 
If a user wants alternatives or variety, you can run the same tool again to get different results. Always mention 
this capability when providing meal plans.

STRUCTURED MEAL EXPANSION: When the system selects an item from a section that mentions choosing sides, sauces, 
or toppings (like "Choice of Two Sides, Sauce and Hushpuppies"), it automatically includes the appropriate 
number of sides and sauces to create a complete meal. This provides realistic meal combinations that match 
how these items are actually served.

PROTEIN FOCUS: When discussing meal plans or food recommendations, always highlight protein content. 
For example: "This meal provides 45g of protein, which is excellent for muscle building" or 
"Consider adding grilled chicken (25g protein) to boost your protein intake."

After receiving the tool result, respond to the user using ONLY the food names in that result; do not invent or add items that are not present.

If the user asks general nutrition questions not requiring a specific meal recommendation, answer normally, 
but always include protein information when relevant.""",
)

@agent.tool
def rank_foods(
    ctx: RunContext[str],
    preferences: str,
    meal_type: str = "any",
    num_results: int = 10,
    allowed_foods: Optional[List[str]] = None,
) -> List[Dict[str, Any]]:
    """
    Ranks food items from the database based on a user's preferences
    and returns a structured list of food items.
    """
    conn = sqlite3.connect("duke_nutrition.db")
    cursor = conn.cursor()

    # Base query
    query = "SELECT name, restaurant, section, calories, protein, total_fat, total_carbs, sodium, dietary_fiber FROM items WHERE calories > 0 AND protein > 0"
    
    if allowed_foods:
        placeholders = ','.join('?' for _ in allowed_foods)
        query += f" AND name IN ({placeholders})"
        params = allowed_foods
    else:
        params = []

    cursor.execute(query, params)
    items = cursor.fetchall()
    conn.close()

    if not items:
        return []

    # Simple preference weighting (can be expanded)
    # This is a basic implementation. A more advanced version could use embeddings.
    pref_lower = preferences.lower()
    
    def score_item(item):
        s = 0
        name, _, _, calories, protein, fat, carbs, sodium, fiber = item
        name = name.lower()

        # Meal-type scoring
        if meal_type == 'breakfast':
            if any(bf_word in name for bf_word in ['egg', 'bacon', 'sausage', 'oatmeal', 'pancake', 'waffle', 'bagel', 'pastry', 'yogurt']):
                s += 50
            if any(ld_word in name for ld_word in ['pasta', 'burger', 'steak', 'sandwich', 'dinner', 'entree']):
                s -= 50
        elif meal_type in ['lunch', 'dinner']:
            if any(ld_word in name for ld_word in ['pasta', 'burger', 'steak', 'sandwich', 'entree', 'chicken', 'beef', 'salmon']):
                s += 50
            if any(bf_word in name for bf_word in ['pancake', 'waffle', 'breakfast']):
                s -= 50

        # Goal-based scoring
        if 'high protein' in pref_lower or 'muscle' in pref_lower:
            s += protein * 2
        if 'low carb' in pref_lower:
            s -= carbs * 2
        if 'low fat' in pref_lower:
            s -= fat
        if 'low calorie' in pref_lower or 'weight loss' in pref_lower:
            s -= calories * 0.1
        if 'high calorie' in pref_lower or 'weight gain' in pref_lower:
            s += calories * 0.1
        
        # Keyword scoring
        for keyword in pref_lower.split():
            if keyword in name:
                s += 20
        
        return s

    sorted_items = sorted(items, key=score_item, reverse=True)

    # Format output as a list of dictionaries
    output_items = []
    for item in sorted_items[:num_results]:
        name, restaurant, section, calories, protein, fat, carbs, sodium, fiber = item
        output_items.append({
            "name": name,
            "restaurant": restaurant,
            "section": section,
            "calories": calories,
            "protein": protein,
            "fat": fat,
            "carbs": carbs,
            "sodium": sodium,
            "fiber": fiber
        })

    return output_items

@agent.tool
def create_meal(
    ctx: RunContext[str],
    preferences: str,
    meal_type: str = "any",
) -> Dict[str, Any]:
    """
    Finds a main dish based on preferences and then uses `compose_complete_meal`
    to build a full meal around it. Returns a structured meal object.
    """
    try:
        # Find a new main item for the meal
        ranked_mains = rank_foods(
            ctx,
            preferences=f"main dish for {meal_type}, {preferences}",
            meal_type=meal_type,
            num_results=5
        )

        if not ranked_mains:
            return {"restaurant": "Not Found", "items": []}

        # Take the top-ranked main item
        main_item = ranked_mains[0]

        # Compose a full meal around the main item
        return compose_complete_meal(ctx, main_item=json.dumps(main_item))

    except Exception as e:
        ctx.log.error(f"Error in create_meal: {e}")
        return {"restaurant": "Error", "items": [{"name": "Could not generate a meal"}]}

@agent.tool
def build_custom_meal(
    ctx: RunContext[str],
    restaurant: str,
    meal_type: str = "bowl",
    preferences: str = "",
) -> str:
    """Build a custom meal (bowl, pizza, pasta, etc.) using the restaurant's structured sections.
    
    Parameters
    ----------
    restaurant : str
        Name of the restaurant (e.g., "Ginger + Soy")
    meal_type : str
        Type of meal to build (e.g., "bowl", "pizza", "pasta")
    preferences : str
        User preferences for ingredients or nutrition goals
    """
    conn = sqlite3.connect("duke_nutrition.db")
    cursor = conn.cursor()

    # Get all sections for this restaurant
    cursor.execute(
        """
        SELECT DISTINCT section 
        FROM items 
        WHERE restaurant = ? 
        ORDER BY section
        """, 
        (restaurant,)
    )
    sections = [row[0] for row in cursor.fetchall()]
    
    # Filter sections related to the meal type
    relevant_sections = []
    meal_keywords = {
        "bowl": ["bowl", "base", "protein", "vegetable", "sauce", "topping"],
        "pizza": ["pizza", "crust", "sauce", "topping"],
        "pasta": ["pasta", "sauce", "protein", "topping"],
        "burger": ["burger", "bread", "protein", "topping"],
        "sandwich": ["sandwich", "bread", "filling", "topping"]
    }
    
    keywords = meal_keywords.get(meal_type.lower(), ["base", "protein", "vegetable", "sauce", "topping"])
    
    for section in sections:
        if any(keyword.lower() in section.lower() for keyword in keywords):
            relevant_sections.append(section)
    
    if not relevant_sections:
        return f"No structured meal options found for {meal_type} at {restaurant}"
    
    # Build the meal by selecting from each relevant section
    meal_components = {}
    
    for section in relevant_sections:
        cursor.execute(
            """
            SELECT name, section, calories, protein, total_fat, total_carbs,
                   sodium, dietary_fiber
            FROM items 
            WHERE restaurant = ? AND section = ?
            ORDER BY name
            """, 
            (restaurant, section)
        )
        
        items = cursor.fetchall()
        if not items:
            continue
            
        # Filter out items with invalid nutrition data
        valid_items = [item for item in items if validate_nutrition_data(item)]
        if not valid_items:
            continue
        
        items = valid_items
            
        # Determine how many items to select from this section
        section_lower = section.lower()
        if "choose one" in section_lower or "base" in section_lower or "protein" in section_lower:
            num_to_select = 1
        elif "choose up to five" in section_lower or "five" in section_lower:
            num_to_select = 5
        elif "choose up to three" in section_lower or "three" in section_lower:
            num_to_select = 3
        elif "choose up to two" in section_lower or "two" in section_lower:
            num_to_select = 2
        elif "sauce" in section_lower and "choose" not in section_lower:
            num_to_select = 1
        else:
            num_to_select = min(3, len(items))  # Default to 3 or fewer
        
        # Select items based on preferences or nutritional balance
        selected_items = []
        
        if preferences:
            # Use simple keyword matching for preferences
            pref_lower = preferences.lower()
            scored_items = []
            
            for item in items:
                score = 0
                item_name_lower = item[0].lower()
                
                # Score based on preference keywords
                for word in pref_lower.split():
                    if word in item_name_lower:
                        score += 2
                    # Nutritional preferences
                    if word in ["healthy", "low-fat", "lean"] and item[4] < 10:  # low fat
                        score += 1
                    if word in ["protein", "high-protein"] and item[3] > 15:  # high protein
                        score += 1
                    if word in ["low-sodium"] and item[6] < 300:  # low sodium
                        score += 1
                    if word in ["fiber", "high-fiber"] and item[7] > 3:  # high fiber
                        score += 1
                
                scored_items.append((score, item))
            
            # Sort by score and select top items
            scored_items.sort(key=lambda x: x[0], reverse=True)
            selected_items = [item[1] for item in scored_items[:num_to_select]]
        else:
            # If no preferences, select items for nutritional balance
            if "protein" in section_lower:
                # For protein, prioritize high protein items
                items_sorted = sorted(items, key=lambda x: x[3], reverse=True)
            elif "vegetable" in section_lower:
                # For vegetables, prioritize high fiber, low calorie
                items_sorted = sorted(items, key=lambda x: (x[7], -x[2]), reverse=True)
            elif "sauce" in section_lower:
                # For sauces, prioritize lower sodium
                items_sorted = sorted(items, key=lambda x: x[6])
            else:
                # Default: prioritize balanced nutrition
                items_sorted = sorted(items, key=lambda x: x[2])  # Sort by calories
            
            selected_items = items_sorted[:num_to_select]
        
        if selected_items:
            meal_components[section] = selected_items
    
    conn.close()
    
    # Format the response
    if not meal_components:
        return f"Could not build a {meal_type} from {restaurant} - no suitable components found"
    
    result = {
        "restaurant": restaurant,
        "meal_type": meal_type,
        "components": {}
    }
    
    total_calories = 0
    total_protein = 0
    total_fat = 0
    total_carbs = 0
    
    for section, items in meal_components.items():
        component_list = []
        for item in items:
            component_info = {
                "name": item[0],
                "calories": item[2],
                "protein": item[3],
                "fat": item[4],
                "carbs": item[5]
            }
            component_list.append(component_info)
            total_calories += item[2] or 0
            total_protein += item[3] or 0
            total_fat += item[4] or 0
            total_carbs += item[5] or 0
        
        result["components"][section] = component_list
    
    result["nutrition_totals"] = {
        "total_calories": total_calories,
        "total_protein": total_protein,
        "total_fat": total_fat,
        "total_carbs": total_carbs
    }
    
    return str(result)

@agent.tool  
def get_allergens(ctx: RunContext[str]) -> str:
    """Get the player's allergens."""
    return ctx.deps

@agent.tool
def filter_foods(
    ctx: RunContext[str],
    min: Optional[Dict[str, float]] = None,
    max: Optional[Dict[str, float]] = None,
) -> List[str]:
    """Return food names that satisfy all numeric constraints.

    Parameters
    ----------
    min : dict of nutrient -> minimum value (inclusive)
    max : dict of nutrient -> maximum value (inclusive)
    """

    min = {k.lower(): v for k, v in (min or {}).items()}
    max = {k.lower(): v for k, v in (max or {}).items()}

    conn = sqlite3.connect("duke_nutrition.db")
    cursor = conn.cursor()

    where_clauses = []
    params: List[float] = []

    for col, bound in min.items():
        where_clauses.append(f"{col} >= ?")
        params.append(bound)

    for col, bound in max.items():
        where_clauses.append(f"{col} <= ?")
        params.append(bound)

    where_sql = "WHERE " + " AND ".join(where_clauses) if where_clauses else ""

    cursor.execute(f"SELECT name FROM items {where_sql}", params)
    rows = cursor.fetchall()
    conn.close()

    return [r[0] for r in rows]

@agent.tool
def get_restaurant_sections(ctx: RunContext[str], restaurant: Optional[str] = None) -> str:
    """Get information about structured meal sections available at restaurants.
    
    Parameters
    ----------
    restaurant : str, optional
        Specific restaurant name. If None, shows all restaurants and their sections.
    """
    conn = sqlite3.connect("duke_nutrition.db")
    cursor = conn.cursor()
    
    if restaurant:
        # Get sections for specific restaurant
        cursor.execute(
            """
            SELECT DISTINCT section 
            FROM items 
            WHERE restaurant = ? 
            ORDER BY section
            """, 
            (restaurant,)
        )
        sections = [row[0] for row in cursor.fetchall()]
        
        if not sections:
            return f"No sections found for restaurant: {restaurant}"
        
        # Group sections by meal type
        grouped_sections = {
            "Build Your Own Bowls": [],
            "Build Your Own Pizza": [],
            "Build Your Own Pasta": [],
            "Build Your Own Burgers/Sandwiches": [],
            "Other Sections": []
        }
        
        for section in sections:
            section_lower = section.lower()
            if "bowl" in section_lower and "build" in section_lower:
                grouped_sections["Build Your Own Bowls"].append(section)
            elif "pizza" in section_lower:
                grouped_sections["Build Your Own Pizza"].append(section)
            elif "pasta" in section_lower:
                grouped_sections["Build Your Own Pasta"].append(section)
            elif any(word in section_lower for word in ["burger", "sandwich", "biscuit"]):
                grouped_sections["Build Your Own Burgers/Sandwiches"].append(section)
            else:
                grouped_sections["Other Sections"].append(section)
        
        result = {
            "restaurant": restaurant,
            "structured_sections": {k: v for k, v in grouped_sections.items() if v}
        }
        
    else:
        # Get all restaurants and their build-your-own options
        cursor.execute(
            """
            SELECT DISTINCT restaurant, section 
            FROM items 
            WHERE section LIKE '%build%' OR section LIKE '%choose%'
            ORDER BY restaurant, section
            """
        )
        
        restaurant_sections = {}
        for row in cursor.fetchall():
            rest_name = row[0]
            section = row[1]
            
            if rest_name not in restaurant_sections:
                restaurant_sections[rest_name] = []
            restaurant_sections[rest_name].append(section)
        
        result = {
            "all_restaurants_with_structured_options": restaurant_sections
        }
    
    conn.close()
    return str(result)

@agent.tool
def build_daily_meal_plan(
    ctx: RunContext[str],
    target_calories: int,
    target_protein: int,
    preferences: str = ""
) -> str:
    """
    Builds a balanced, daily meal plan with diverse restaurants, ensuring meals are not duplicated.
    """
    num_meals = 3 # Assuming breakfast, lunch, dinner
    per_meal_calories = target_calories // num_meals
    per_meal_protein = target_protein // num_meals
    
    meal_plan = {}
    used_items = set()
    used_restaurants = set()
    
    for meal_type in ["breakfast", "lunch", "dinner"]:
        # Find a main dish that fits the preferences and calorie/protein targets
        main_items = rank_foods(
            ctx,
            preferences=f"main dish for {meal_type}, {preferences}",
            meal_type=meal_type,
            num_results=40 # Get a larger selection to ensure variety
        )
        
        # Filter out already used items
        available_mains = [item for item in main_items if item['name'] not in used_items]

        if not available_mains:
            continue

        # Try to pick from a new restaurant first
        diverse_mains = [item for item in available_mains if item['restaurant'] not in used_restaurants]
        
        # If we have options from new restaurants, use them. Otherwise, fall back to what's available.
        selection_pool = diverse_mains if diverse_mains else available_mains
        
        # Find the main item that is closest to our per-meal calorie goal from the selected pool
        best_main = min(selection_pool, key=lambda x: abs(x['calories'] - per_meal_calories))

        # Build a complete meal around this main item
        full_meal = compose_complete_meal(ctx, main_item=json.dumps(best_main))
        
        # Add the full meal to the plan and track what's been used
        if full_meal and full_meal.get("items"):
            meal_plan[meal_type] = full_meal
            used_restaurants.add(full_meal['restaurant'])
            for item in full_meal['items']:
                used_items.add(item['name'])

    # Format the plan into a string for the response
    final_plan_str = []
    if meal_plan.get("breakfast"):
        final_plan_str.append(format_meal_to_string("Breakfast", meal_plan["breakfast"]))
    if meal_plan.get("lunch"):
        final_plan_str.append(format_meal_to_string("Lunch", meal_plan["lunch"]))
    if meal_plan.get("dinner"):
        final_plan_str.append(format_meal_to_string("Dinner", meal_plan["dinner"]))
        
    return "\n\n".join(filter(None, final_plan_str))

@agent.tool
def check_nutrition_data_quality(ctx: RunContext[str], show_invalid: bool = True) -> str:
    """Check the quality of nutrition data in the database and optionally show invalid items.
    
    Parameters
    ----------
    show_invalid : bool
        Whether to show examples of items with invalid nutrition data
    """
    conn = sqlite3.connect("duke_nutrition.db")
    cursor = conn.cursor()
    
    cursor.execute(
        """
        SELECT name, restaurant, section, calories, protein, total_fat, total_carbs, sodium
        FROM items 
        WHERE calories IS NOT NULL
        ORDER BY restaurant, name
        """
    )
    
    all_items = cursor.fetchall()
    conn.close()
    
    if not all_items:
        return "No items found in database"
    
    valid_items = []
    invalid_items = []
    
    for item in all_items:
        if validate_nutrition_data(item):
            valid_items.append(item)
        else:
            invalid_items.append(item)
    
    result = {
        "total_items": len(all_items),
        "valid_items": len(valid_items),
        "invalid_items": len(invalid_items),
        "validity_percentage": round((len(valid_items) / len(all_items)) * 100, 1)
    }
    
    if show_invalid and invalid_items:
        # Show top 10 most problematic items
        result["examples_of_invalid_items"] = []
        for item in invalid_items[:10]:
            result["examples_of_invalid_items"].append({
                "name": item[0],
                "restaurant": item[1], 
                "calories": item[3],
                "protein": item[4],
                "fat": item[5],
                "carbs": item[6],
                "sodium": item[7]
            })
    
    return str(result)

@agent.tool
def get_restaurant_summary(ctx: RunContext[str], restaurant: str) -> str:
    """
    Get a summary of the types of food available at a given restaurant.
    """
    conn = sqlite3.connect("duke_nutrition.db")
    cursor = conn.cursor()
    
    cursor.execute(
        "SELECT DISTINCT section FROM items WHERE restaurant = ? AND section IS NOT 'General'",
        (restaurant,)
    )
    
    sections = [row[0] for row in cursor.fetchall()]
    conn.close()
    
    if not sections:
        return f"No specific food categories found for {restaurant}."
    
    return f"Restaurant {restaurant} has the following food categories: {', '.join(sections)}"

def format_meal_to_string(meal_name: str, meal_data: Dict) -> str:
    """Formats a single meal object into a string with prominent protein information."""
    if not meal_data or not meal_data.get("items"):
        return ""
    
    lines = [f"{meal_name.capitalize()} — {meal_data.get('restaurant', 'Unknown')}"]
    total_protein = 0
    
    for item in meal_data["items"]:
        lines.append(f"- {item['name']}")
        if item.get("calories"):
            lines.append(f"  - Calories: {item['calories']} kcal")
        if item.get("protein"):
            protein = item['protein']
            total_protein += protein
            lines.append(f"  - Protein: {protein}g")
    
    # Add total protein for the meal
    if total_protein > 0:
        lines.append(f"\n📊 Total Protein for {meal_name.capitalize()}: {total_protein}g")
    
    return "\n".join(lines)

@agent.tool
def compose_complete_meal(
    ctx: RunContext[str],
    main_item: str,
) -> Dict[str, Any]:
    """
    Takes a main food item (as a JSON string) and finds complementary
    sides from the same restaurant to create a complete meal object.
    """
    main_item_data = json.loads(main_item)
    restaurant = main_item_data.get("restaurant")

    if not restaurant:
        return {
            "restaurant": "Unknown",
            "items": [main_item_data]
        }

    # Find potential sides from the same restaurant
    conn = sqlite3.connect("duke_nutrition.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT name, restaurant, section, calories, protein FROM items WHERE restaurant = ? AND section LIKE '%side%'",
        (restaurant,)
    )
    sides = cursor.fetchall()
    conn.close()

    # Simple logic: pick one or two sides
    meal_items = [main_item_data]
    if sides:
        # Prioritize common sides like fries, salad, etc.
        sorted_sides = sorted(sides, key=lambda s: 1 if any(kw in s[0].lower() for kw in ['fries', 'salad', 'rice', 'vegetable']) else 0, reverse=True)
        meal_items.append({
            "name": sorted_sides[0][0],
            "calories": sorted_sides[0][3],
            "protein": sorted_sides[0][4],
            "restaurant": sorted_sides[0][1]
        })

    return {
        "restaurant": restaurant,
        "items": meal_items
    }

@agent.tool
def add_item_to_meal(
    ctx: RunContext[str],
    meal_to_add_to: str,
    item_name: str,
    current_plan_json: str,
) -> Dict[str, Any]:
    """
    Adds a single food item to a specific meal in the current meal plan.
    Use this when the user wants to add a specific item to an existing meal.
    """
    try:
        current_plan = json.loads(current_plan_json)
        meal_key = meal_to_add_to.lower()

        # Find the requested item in the database
        conn = sqlite3.connect("duke_nutrition.db")
        cursor = conn.cursor()
        # Use LIKE to find items with similar names
        cursor.execute(
            "SELECT name, restaurant, calories, protein FROM items WHERE name LIKE ? ORDER BY length(name) ASC LIMIT 1",
            (f"%{item_name}%",)
        )
        item_data = cursor.fetchone()
        conn.close()

        if not item_data:
            # If item not found, just return the original plan
            return current_plan

        new_item = {
            "name": item_data[0],
            "restaurant": item_data[1],
            "calories": item_data[2],
            "protein": item_data[3],
        }

        # If the meal doesn't exist yet (e.g., adding a snack), create it
        if not current_plan.get(meal_key):
            current_plan[meal_key] = {
                "restaurant": new_item["restaurant"],
                "items": []
            }

        # Add the new item to the specified meal
        current_plan[meal_key]["items"].append(new_item)
        
        # If the meal restaurant was generic, update it
        if current_plan[meal_key]["restaurant"] in ["Unknown", "Multiple Locations"]:
             current_plan[meal_key]["restaurant"] = new_item["restaurant"]

        return current_plan

    except Exception as e:
        ctx.log.error(f"Error in add_item_to_meal: {e}")
        return json.loads(current_plan_json) # Fallback to original plan

@agent.tool
def replace_meal(
    ctx: RunContext[str],
    meal_to_replace: str,
    preferences: str,
    current_plan_json: str,
) -> Dict[str, Any]:
    """
    Replaces a single meal in an existing plan with a new, cohesively built meal.
    """
    try:
        current_plan = json.loads(current_plan_json)
        meal_to_replace = meal_to_replace.lower()

        # Find a new main item for the meal
        ranked_mains = rank_foods(
            ctx,
            preferences=f"main dish for {meal_to_replace}, {preferences}",
            meal_type=meal_to_replace,
            num_results=5  # Get a few options
        )

        if not ranked_mains:
            return current_plan # Return original plan if no items found

        # Take the top-ranked main item
        main_item = ranked_mains[0]

        # Compose a full meal around the main item
        new_meal = compose_complete_meal(ctx, main_item=json.dumps(main_item))

        # Update the plan with the new, complete meal, but only if it's valid
        if new_meal and new_meal.get("items"):
            current_plan[meal_to_replace] = new_meal
        
        return current_plan

    except Exception as e:
        ctx.log.error(f"Error in replace_meal: {e}")
        # On failure, return the original plan to avoid losing it
        return json.loads(current_plan_json)

def main():
    """Simple CLI loop to chat with the agent while preserving context."""
    deps_input = input("Any dietary restrictions? (press Enter for none): ").strip()
    deps = deps_input if deps_input else None

    message_history = None  # will hold full conversation between turns

    print("Type 'exit' to quit. Start chatting!\n")

    try:
        while True:
            user_prompt = input("You: ").strip()
            if user_prompt.lower() in {"exit", "quit", "stop"}:
                print("Good-bye!")
                break

            # Run the agent with prior history so the conversation continues
            result = agent.run_sync(
                user_prompt,
                deps=deps,
                message_history=message_history,
            )

            print(f"Agent: {result.output}\n")

            # Store updated history for the next turn
            message_history = result.all_messages()
    except KeyboardInterrupt:
        print("\nInterrupted. Bye!")


# Allow `python agent.py` to start the interactive chat
if __name__ == "__main__":
    import sys
    if "--debug" in sys.argv:
        agent.to_cli_sync()
    else:
        main()   # homemade loop