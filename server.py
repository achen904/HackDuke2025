from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import logging
import re
from typing import Dict, Any, List, Optional
import traceback

# Import the agent from agent.py
from agent import agent as duke_agent_instance

app = Flask(__name__, static_folder='.')
CORS(app)

# Set up logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def parse_agent_response(agent_response: str) -> Dict[str, Any]:
    """
    Parse the agent's string response and convert it to structured meal plan data.
    The agent returns a format with meal headers using em dash, restaurant info, and food items.
    """
    try:
        # Initialize the meal plan structure
        meal_plan = {
            "dayName": "Your Personalized Meal Plan",
            "breakfast": None,
            "lunch": None,
            "dinner": None,
            "snacks": None
        }
        
        # Split the response into lines and parse
        lines = [line.rstrip() for line in agent_response.strip().split('\n')]
        current_meal = None
        current_restaurant = None
        current_food_item = None
        current_nutrition = {}
        meal_items = []
        
        i = 0
        while i < len(lines):
            line = lines[i]
            if not line.strip():
                i += 1
                continue
                
            line_lower = line.lower()
            
            # Skip summary sections entirely
            if any(skip_phrase in line_lower for skip_phrase in [
                'daily nutrition summary', 'nutrition summary', 'total daily', 
                'daily totals', 'summary:', 'if you\'d like to see', 'alternative options'
            ]):
                # Skip the rest of the response as it's summary info
                break
            
            # Check for meal type headers with em dash: "Breakfast — Restaurant"
            if '—' in line and any(meal in line_lower for meal in ['breakfast', 'lunch', 'dinner', 'snack']):
                # Save previous food item if exists
                if current_food_item:
                    item = {
                        "name": current_food_item,
                        "calories": current_nutrition.get('calories'),
                        "protein": current_nutrition.get('protein'),
                        "restaurant": current_restaurant,
                        "description": f"From {current_restaurant}"
                    }
                    meal_items.append(item)
                
                # Save previous meal if exists
                if current_meal and meal_items:
                    # Determine primary restaurant - if all items from same place, use that; else "Multiple Locations"
                    restaurants = [item.get('restaurant', '') for item in meal_items if item.get('restaurant')]
                    unique_restaurants = list(set(restaurants))
                    primary_restaurant = unique_restaurants[0] if len(unique_restaurants) == 1 else "Multiple Locations"
                    
                    meal_plan[current_meal] = {
                        "restaurant": primary_restaurant,
                        "items": meal_items
                    }
                
                # Parse new meal header: "Breakfast — Restaurant"
                parts = line.split('—', 1)
                meal_part = parts[0].strip().lower()
                restaurant_part = parts[1].strip() if len(parts) > 1 else ""
                
                # Determine meal type
                if 'breakfast' in meal_part:
                    current_meal = 'breakfast'
                elif 'lunch' in meal_part:
                    current_meal = 'lunch'
                elif 'dinner' in meal_part:
                    current_meal = 'dinner'
                elif 'snack' in meal_part:
                    current_meal = 'snacks'
                
                current_restaurant = restaurant_part if restaurant_part else "Unknown Location"
                meal_items = []
                current_food_item = None
                current_nutrition = {}
                i += 1
                continue
            
            # Check for food item lines starting with "-"
            if line.startswith('- ') and current_meal:
                food_line = line[2:].strip()  # Remove "- " prefix
                
                # Skip if this looks like a nutrition summary line
                if any(food_line.lower().startswith(term) for term in [
                    'calories:', 'protein:', 'fat:', 'total fat:', 'carbs:', 'carbohydrates:', 
                    'sodium:', 'fiber:', 'sugar:', 'daily', 'total', 'if you'
                ]):
                    i += 1
                    continue
                
                # Save previous food item if exists
                if current_food_item:
                    item = {
                        "name": current_food_item,
                        "calories": current_nutrition.get('calories'),
                        "protein": current_nutrition.get('protein'),
                        "restaurant": current_restaurant,
                        "description": f"From {current_restaurant}"
                    }
                    meal_items.append(item)
                
                # Set new food item
                current_food_item = food_line
                current_nutrition = {}
                
                # Look ahead for nutrition information (indented lines)
                j = i + 1
                while j < len(lines) and (lines[j].startswith('  - ') or lines[j].startswith('    ')):
                    nutrition_line = lines[j].strip()
                    
                    # Remove leading "- " if present
                    if nutrition_line.startswith('- '):
                        nutrition_line = nutrition_line[2:].strip()
                    
                    # Parse nutrition values
                    if nutrition_line.lower().startswith('calories:'):
                        cal_match = re.search(r'calories:\s*(\d+)', nutrition_line, re.IGNORECASE)
                        if cal_match:
                            current_nutrition['calories'] = int(cal_match.group(1))
                    
                    elif nutrition_line.lower().startswith('protein:'):
                        protein_match = re.search(r'protein:\s*(\d+(?:\.\d+)?)', nutrition_line, re.IGNORECASE)
                        if protein_match:
                            current_nutrition['protein'] = float(protein_match.group(1))
                    
                    j += 1
                
                # Set i to continue from after the nutrition lines
                i = j
                continue
            
            i += 1
        
        # Save the final item and meal
        if current_food_item:
            item = {
                "name": current_food_item,
                "calories": current_nutrition.get('calories'),
                "protein": current_nutrition.get('protein'),
                "restaurant": current_restaurant,
                "description": f"From {current_restaurant}"
            }
            meal_items.append(item)
        
        if current_meal and meal_items:
            # Determine primary restaurant for final meal
            restaurants = [item.get('restaurant', '') for item in meal_items if item.get('restaurant')]
            unique_restaurants = list(set(restaurants))
            primary_restaurant = unique_restaurants[0] if len(unique_restaurants) == 1 else "Multiple Locations"
            
            meal_plan[current_meal] = {
                "restaurant": primary_restaurant,
                "items": meal_items
            }
        
        return meal_plan
        
    except Exception as e:
        logger.error(f"Error parsing agent response: {e}")
        logger.error(f"Agent response was: {agent_response}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        # Return a basic structure
        return {
            "dayName": "Your Meal Plan",
            "breakfast": None,
            "lunch": None,
            "dinner": None,
            "snacks": None
        }

def parse_food_item_inline(item_text: str) -> Optional[Dict[str, Any]]:
    """
    Parse a single food item from inline format.
    Expected format: "Restaurant: Food Name (nutrition info)"
    """
    try:
        import re
        
        item = {
            "name": "",
            "calories": None,
            "protein": None,
            "description": ""
        }
        
        # Skip lines that look like summary headers or totals
        item_lower = item_text.lower().strip()
        if (item_lower in ['calories', 'protein', 'fat', 'carbohydrates', 'sodium', 'fiber', 'sugar', 'dietary fiber'] or
            item_lower.startswith('total ') or
            item_lower.startswith('daily ') or
            item_lower.startswith('calories:') or
            item_lower.startswith('protein:') or
            item_lower.startswith('fat:') or
            item_lower.startswith('carbs:') or
            item_lower.startswith('sodium:') or
            item_lower.startswith('fiber:') or
            'summary' in item_lower or
            'this plan' in item_lower or
            'nutritional summary' in item_lower):
            return None
        
        # Check for format: "Restaurant: Food Name (nutrition info)"
        if ':' in item_text and '(' in item_text and ')' in item_text:
            # Split on the first colon to get restaurant and food+nutrition
            colon_index = item_text.find(':')
            restaurant = item_text[:colon_index].strip()
            food_and_nutrition = item_text[colon_index+1:].strip()
            
            # Extract food name and nutrition from parentheses
            paren_start = food_and_nutrition.find('(')
            if paren_start > 0:
                food_name = food_and_nutrition[:paren_start].strip()
                paren_end = food_and_nutrition.rfind(')')
                nutrition_part = food_and_nutrition[paren_start+1:paren_end].strip()
                
                item["name"] = food_name
                item["description"] = f"From {restaurant}"
                
                # Parse nutrition from parentheses (comma-separated)
                nutrition_items = [n.strip() for n in nutrition_part.split(',')]
                for nutrition_item in nutrition_items:
                    # Extract calories (look for "560 kcal")
                    cal_match = re.search(r'(\d+)\s*kcal', nutrition_item, re.IGNORECASE)
                    if cal_match:
                        item["calories"] = int(cal_match.group(1))
                        continue
                    
                    # Extract protein (look for "29g protein")
                    protein_match = re.search(r'(\d+(?:\.\d+)?)\s*g\s*protein', nutrition_item, re.IGNORECASE)
                    if protein_match:
                        item["protein"] = float(protein_match.group(1))
                        continue
                
                return item
        
        # Check for format with parentheses only: "Food Name (nutrition info)"
        elif '(' in item_text and ')' in item_text:
            paren_start = item_text.find('(')
            paren_end = item_text.rfind(')')
            
            if paren_start > 0:
                name_part = item_text[:paren_start].strip()
                nutrition_part = item_text[paren_start+1:paren_end].strip()
                
                item["name"] = name_part
                
                # Parse nutrition from parentheses
                nutrition_items = [n.strip() for n in nutrition_part.split(',')]
                for nutrition_item in nutrition_items:
                    # Extract calories
                    cal_match = re.search(r'(\d+)\s*kcal', nutrition_item, re.IGNORECASE)
                    if cal_match:
                        item["calories"] = int(cal_match.group(1))
                        continue
                    
                    # Extract protein
                    protein_match = re.search(r'(\d+(?:\.\d+)?)\s*g\s*protein', nutrition_item, re.IGNORECASE)
                    if protein_match:
                        item["protein"] = float(protein_match.group(1))
                        continue
                
                return item
        
        # Check for format with colon only: "Restaurant: Food Name"
        elif ':' in item_text:
            colon_index = item_text.find(':')
            restaurant = item_text[:colon_index].strip()
            food_name = item_text[colon_index+1:].strip()
            
            item["name"] = food_name
            item["description"] = f"From {restaurant}"
            return item
        
        # If no special format recognized, return None to fall back to other parsing
        return None
            
    except Exception as e:
        logger.error(f"Error parsing inline food item '{item_text}': {e}")
        return None

def parse_food_item(item_text: str) -> Optional[Dict[str, Any]]:
    """
    Parse a single food item from text format.
    Expected formats:
    - "Food Name (123 cal, 45g protein)"
    - "Food Name - 123 calories, 45g protein"
    - "Food Name"
    """
    try:
        item = {
            "name": "",
            "calories": None,
            "protein": None,
            "description": ""
        }
        
        # Clean up the text
        text = item_text.strip()
        if text.startswith('- '):
            text = text[2:].strip()
        if text.startswith('• '):
            text = text[2:].strip()
            
        # Extract calories and protein if present
        import re
        
        # Look for patterns like (123 cal, 45g protein) or (123 calories, 45g protein)
        nutrition_pattern = r'\(([^)]+)\)'
        nutrition_match = re.search(nutrition_pattern, text)
        
        if nutrition_match:
            nutrition_text = nutrition_match.group(1)
            # Remove the nutrition info from the name
            item["name"] = text.replace(nutrition_match.group(0), "").strip()
            
            # Extract calories
            cal_match = re.search(r'(\d+)\s*(?:cal|calories)', nutrition_text, re.IGNORECASE)
            if cal_match:
                item["calories"] = int(cal_match.group(1))
            
            # Extract protein
            protein_match = re.search(r'(\d+(?:\.\d+)?)\s*g?\s*protein', nutrition_text, re.IGNORECASE)
            if protein_match:
                item["protein"] = float(protein_match.group(1))
        else:
            # Look for nutrition info in different formats
            # Pattern: "Food Name - 123 calories, 45g protein"
            dash_pattern = r'^(.+?)\s*-\s*(.+)$'
            dash_match = re.match(dash_pattern, text)
            
            if dash_match:
                item["name"] = dash_match.group(1).strip()
                nutrition_text = dash_match.group(2).strip()
                
                # Extract calories
                cal_match = re.search(r'(\d+)\s*(?:cal|calories)', nutrition_text, re.IGNORECASE)
                if cal_match:
                    item["calories"] = int(cal_match.group(1))
                
                # Extract protein
                protein_match = re.search(r'(\d+(?:\.\d+)?)\s*g?\s*protein', nutrition_text, re.IGNORECASE)
                if protein_match:
                    item["protein"] = float(protein_match.group(1))
                    
                # Rest is description
                remaining = nutrition_text
                if cal_match:
                    remaining = remaining.replace(cal_match.group(0), "")
                if protein_match:
                    remaining = remaining.replace(protein_match.group(0), "")
                remaining = remaining.strip(" ,")
                if remaining:
                    item["description"] = remaining
            else:
                # Just a food name
                item["name"] = text
        
        # Return the item if we have at least a name
        if item["name"]:
            return item
        else:
            return None
            
    except Exception as e:
        logger.error(f"Error parsing food item '{item_text}': {e}")
        return {"name": item_text, "calories": None, "protein": None, "description": ""}

def build_agent_prompt(user_goals: Dict[str, Any]) -> str:
    """
    Build a prompt for the agent based on user goals.
    This function now handles both initial creation and refinement.
    """
    # Check if this is a refinement of an existing plan
    if user_goals.get('currentPlan') and user_goals.get('specificGoals'):
        current_plan_json = json.dumps(user_goals['currentPlan'])
        user_request = user_goals['specificGoals']
        
        prompt = f"""You are a helpful and conversational meal plan assistant.
        The user wants to discuss their current meal plan. Their request is: "{user_request}"

        Your primary goal is to be helpful and chat with the user. However, you also have tools you can use.

        - If the user's request is a clear command to ADD an item (e.g., "add fries to lunch"), use the `add_item_to_meal` tool.
        - If the user's request is a clear command to REPLACE a meal (e.g., "I want a different dinner"), use the `replace_meal` tool.
        - For anything else (e.g., asking a question, making a comment), respond conversationally as a helpful assistant. DO NOT use a tool if the user is not asking for a specific change.

        The user's current meal plan is provided here for your context:
        {json.dumps(user_goals['currentPlan'], indent=2)}
        
        You must always pass the `current_plan_json` to any tool you use.
        """
        return prompt

    # --- This is the logic for initial plan creation ---
    prompt_parts = []
    
    # Add dietary restrictions
    if user_goals.get('dietaryRestrictions'):
        restrictions = ', '.join(user_goals['dietaryRestrictions'])
        prompt_parts.append(f"Dietary restrictions: {restrictions}")
    
    if user_goals.get('otherDietaryNotes'):
        prompt_parts.append(f"Additional dietary notes: {user_goals['otherDietaryNotes']}")
    
    # Add primary goal
    if user_goals.get('primaryGoal'):
        goal_map = {
            'weightLoss': 'weight loss',
            'weightGain': 'weight gain', 
            'muscleGain': 'muscle gain',
            'maintainWeight': 'maintain weight',
            'healthyEating': 'general healthy eating'
        }
        goal = goal_map.get(user_goals['primaryGoal'], user_goals['primaryGoal'])
        prompt_parts.append(f"Primary goal: {goal}")
    
    # Add specific goals
    if user_goals.get('specificGoals'):
        prompt_parts.append(f"Specific targets: {user_goals['specificGoals']}")
    
    # Determine meals needed
    meals_consumed = user_goals.get('mealsConsumed', {})
    needed_meals = []
    if meals_consumed.get('breakfast', False):
        needed_meals.append('breakfast')
    if meals_consumed.get('lunch', False):
        needed_meals.append('lunch')
    if meals_consumed.get('dinner', False):
        needed_meals.append('dinner')
    if meals_consumed.get('snacks', False):
        needed_meals.append('snacks')
    
    if needed_meals:
        prompt_parts.append(f"Plan meals for: {', '.join(needed_meals)}")
    
    # Build the final prompt
    prompt = "Create a daily meal plan with the following requirements:\n" + '\n'.join(f"- {part}" for part in prompt_parts)
    
    prompt += "\n\nFirst, use the `get_restaurant_summary` tool to understand the types of food available at a few different restaurants. Then, proceed with meal creation."

    # Add specific instructions to use the tools
    if 'breakfast' in needed_meals and 'lunch' in needed_meals and 'dinner' in needed_meals:
        prompt += "\n\nPlease use the `build_daily_meal_plan` tool to create a comprehensive meal plan that meets these requirements. Make sure to include specific food items from Duke dining locations with nutritional information."
    else:
        prompt += "\n\nPlease use the `create_meal` tool for each requested meal type to provide specific food recommendations from Duke dining locations."
    
    # Add detailed formatting instructions
    prompt += """

IMPORTANT OUTPUT FORMAT REQUIREMENTS:
1. Format each meal header as: "Meal Type — Restaurant Name" (using em dash)
2. List each food item with "- Food Name"
3. Include nutrition details on indented lines under each food item
4. Always include restaurant information for every meal
5. Include at least calories and protein for each food item
6. Use this exact format:

Breakfast — Restaurant Name
- Food Item Name
  - Calories: XXX kcal
  - Protein: XXg

Lunch — Restaurant Name  
- Food Item Name
  - Calories: XXX kcal
  - Protein: XXg

Dinner — Restaurant Name
- Food Item Name
  - Calories: XXX kcal
  - Protein: XXg

7. Ensure every meal has a restaurant name specified
8. Do not include summary sections or alternative suggestions"""
    
    return prompt

@app.route('/api/get_meal_plan', methods=['POST'])
def get_meal_plan():
    """
    Main endpoint to generate meal plans based on user goals.
    """
    try:
        # Get user goals from request
        user_goals = request.get_json()
        
        if not user_goals:
            return jsonify({"error": "No user goals provided"}), 400
        
        logger.info(f"Received meal plan request: {user_goals}")
        
        # Build prompt for the agent
        prompt = build_agent_prompt(user_goals)
        logger.info(f"Generated prompt: {prompt}")
        
        # Call the agent to get meal plan
        # The agent expects a string context, so we'll pass an empty string or relevant context
        try:
            agent_response = duke_agent_instance.run_sync(prompt, deps="")
            logger.info(f"Agent response type: {type(agent_response)}")
            logger.info(f"Agent response: {agent_response}")
            
            # Check if the agent returned a complete plan object (from replace_meal)
            if isinstance(agent_response.data, dict):
                meal_plan = agent_response.data
                # We need to format this dict back to text for the chatbot display
                agent_text = ""
                if meal_plan.get("breakfast"):
                    agent_text += format_meal_to_string("breakfast", meal_plan["breakfast"]) + "\n\n"
                if meal_plan.get("lunch"):
                    agent_text += format_meal_to_string("lunch", meal_plan["lunch"]) + "\n\n"
                if meal_plan.get("dinner"):
                    agent_text += format_meal_to_string("dinner", meal_plan["dinner"]) + "\n\n"
                if meal_plan.get("snacks"):
                    agent_text += format_meal_to_string("snacks", meal_plan["snacks"]) + "\n\n"
                agent_text = agent_text.strip()
            else:
                # Original flow: parse the text response from the agent
                if hasattr(agent_response, 'output'):
                    agent_text = str(agent_response.output)
                elif hasattr(agent_response, 'data'):
                    agent_text = str(agent_response.data)
                else:
                    agent_text = str(agent_response)
                
                logger.info(f"Agent text for parsing: {agent_text}")
                meal_plan = parse_agent_response(agent_text)

        except Exception as e:
            logger.error(f"Error calling agent: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return jsonify({
                "error": "Failed to call nutrition agent",
                "details": str(e)
            }), 500
        
        # Filter meals based on user preferences
        meals_consumed = user_goals.get('mealsConsumed', {})
        if not meals_consumed.get('breakfast', False):
            meal_plan['breakfast'] = None
        if not meals_consumed.get('lunch', False):
            meal_plan['lunch'] = None
        if not meals_consumed.get('dinner', False):
            meal_plan['dinner'] = None
        if not meals_consumed.get('snacks', False):
            meal_plan['snacks'] = None
        
        logger.info(f"Final meal plan: {meal_plan}")
        
        return jsonify({
            "mealPlan": meal_plan,
            "rawText": agent_text
        })
        
    except Exception as e:
        logger.error(f"Error generating meal plan: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "error": "Failed to generate meal plan",
            "details": str(e)
        }), 500

def format_meal_to_string(meal_name: str, meal_data: Dict) -> str:
    """Helper to format a meal object into a string, to be used for agent's text response."""
    if not meal_data or not meal_data.get("items"):
        return ""
    
    lines = [f"{meal_name.capitalize()} — {meal_data.get('restaurant', 'Unknown')}"]
    for item in meal_data["items"]:
        lines.append(f"- {item['name']}")
        if item.get("calories"):
            lines.append(f"  - Calories: {item['calories']} kcal")
        if item.get("protein"):
            lines.append(f"  - Protein: {item['protein']}g")
    return "\n".join(lines)

@app.route('/api/chat', methods=['POST'])
def chat_with_agent():
    """
    Direct communication endpoint with the AI agent for chat interactions.
    """
    try:
        data = request.get_json()
        user_message = data.get('message', '')
        current_plan = data.get('currentPlan', None)
        
        if not user_message:
            return jsonify({"error": "No message provided"}), 400
        
        logger.info(f"Chat request: {user_message}")
        
        # Build a conversational prompt for the agent
        prompt = f"""
User message: {user_message}

{f"Current meal plan: {json.dumps(current_plan, indent=2)}" if current_plan else "No current meal plan."}

Please respond to the user's request in a conversational manner. You can:
1. Answer questions about nutrition
2. Suggest modifications to the current meal plan
3. Provide dietary advice
4. Explain food choices and their nutritional benefits
5. Help with meal planning strategies

Respond naturally and helpfully.
"""
        
        # Call the agent directly
        try:
            agent_response = duke_agent_instance.run_sync(prompt, deps="")
            
            # Extract the response text
            if hasattr(agent_response, 'output'):
                response_text = str(agent_response.output)
            elif hasattr(agent_response, 'data'):
                response_text = str(agent_response.data)
            else:
                response_text = str(agent_response)
            
            logger.info(f"Agent chat response: {response_text}")
            
            return jsonify({
                "response": response_text,
                "success": True
            })
            
        except Exception as e:
            logger.error(f"Error calling agent for chat: {e}")
            return jsonify({
                "error": "Failed to get response from agent",
                "details": str(e)
            }), 500
            
    except Exception as e:
        logger.error(f"Error in chat endpoint: {e}")
        return jsonify({
            "error": "Failed to process chat request",
            "details": str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Simple health check endpoint.
    """
    return jsonify({"status": "healthy", "message": "Duke Eats API is running"})

# Parser is working correctly

@app.route('/')
def serve_index():
    """
    Serve the main HTML file.
    """
    return send_from_directory('dist', 'index.html')

@app.route('/<path:filename>')
def serve_static_files(filename):
    """
    Serve static files (JS, CSS, etc.)
    """
    # Try dist directory first, then fall back to current directory
    try:
        return send_from_directory('dist', filename)
    except FileNotFoundError:
        return send_from_directory('.', filename)


@app.after_request
def add_security_headers(response):
    """Add security headers to all responses"""
    # Force HTTPS
    hsts = 'max-age=63072000; includeSubDomains; preload'
    response.headers['Strict-Transport-Security'] = hsts
    # Prevent mixed content issues
    response.headers['Content-Security-Policy'] = 'upgrade-insecure-requests'
    # Additional security headers
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'SAMEORIGIN'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    return response


if __name__ == '__main__':
    # Run the development server
    app.run(debug=True, host='0.0.0.0', port=3000)
