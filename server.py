from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
import json
import logging
import os
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
    The agent returns a format with meal headers, restaurant headers, and food items.
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
        lines = [line.rstrip() for line in agent_response.strip().split('\n')]  # Keep original spacing
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
            
            # Check for meal type headers (with or without colon)
            if any(meal in line_lower.rstrip(':') for meal in ['breakfast', 'lunch', 'dinner', 'snack']):
                # Save previous meal if exists
                if current_meal and meal_items:
                    meal_plan[current_meal] = {
                        "restaurant": current_restaurant or "Multiple Locations",
                        "items": meal_items
                    }
                
                # Determine meal type
                meal_text = line_lower.rstrip(':')
                if 'breakfast' in meal_text:
                    current_meal = 'breakfast'
                elif 'lunch' in meal_text:
                    current_meal = 'lunch'
                elif 'dinner' in meal_text:
                    current_meal = 'dinner'
                elif 'snack' in meal_text:
                    current_meal = 'snacks'
                
                meal_items = []
                current_food_item = None
                current_restaurant = None
                current_nutrition = {}
                i += 1
                continue
            

            
            # Check for food item lines (format: "- Food Name (Restaurant)")
            if line.startswith('- ') and current_meal:
                food_line = line[2:].strip()  # Remove "- " prefix
                
                # Skip summary/nutrition lines that start with nutrition terms
                food_line_lower = food_line.lower()
                if any(food_line_lower.startswith(term) for term in [
                    'calories:', 'protein:', 'fat:', 'carbs:', 'carbohydrates:', 
                    'sodium:', 'fiber:', 'sugar:', 'daily', 'total'
                ]):
                    i += 1
                    continue
                
                # Save previous food item if exists
                if current_food_item and current_restaurant:
                    item = {
                        "name": current_food_item,
                        "calories": current_nutrition.get('calories'),
                        "protein": current_nutrition.get('protein'),
                        "description": f"From {current_restaurant}"
                    }
                    meal_items.append(item)
                
                # Extract food name and restaurant from "Food Name (Restaurant)" format
                if '(' in food_line and ')' in food_line:
                    # Split on the last opening parenthesis to handle foods with parentheses in name
                    last_paren = food_line.rfind('(')
                    current_food_item = food_line[:last_paren].strip()
                    current_restaurant = food_line[last_paren+1:].rstrip(')').strip()
                else:
                    # No restaurant info in parentheses
                    current_food_item = food_line
                    current_restaurant = "Unknown Location"
                
                current_nutrition = {}
                
                # Look ahead for nutrition information
                j = i + 1
                while j < len(lines) and lines[j].startswith('  - '):
                    nutrition_line = lines[j][4:].strip()  # Remove "  - "
                    
                    # Parse nutrition
                    if nutrition_line.lower().startswith('calories:'):
                        cal_match = re.search(r'calories:\s*(\d+)', nutrition_line, re.IGNORECASE)
                        if cal_match:
                            current_nutrition['calories'] = int(cal_match.group(1))
                    
                    elif nutrition_line.lower().startswith('protein:'):
                        protein_match = re.search(r'protein:\s*(\d+(?:\.\d+)?)', nutrition_line, re.IGNORECASE)
                        if protein_match:
                            current_nutrition['protein'] = float(protein_match.group(1))
                    
                    j += 1
                
                i = j  # Skip the nutrition lines we just processed
                continue
            
            i += 1
        
        # Save the final item and meal
        if current_food_item and current_restaurant:
            item = {
                "name": current_food_item,
                "calories": current_nutrition.get('calories'),
                "protein": current_nutrition.get('protein'),
                "description": f"From {current_restaurant}"
            }
            meal_items.append(item)
        
        if current_meal and meal_items:
            meal_plan[current_meal] = {
                "restaurant": current_restaurant or "Multiple Locations",
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
            parts = item_text.split(':', 1)
            restaurant = parts[0].strip()
            food_and_nutrition = parts[1].strip()
            
            # Extract food name and nutrition from parentheses
            paren_match = re.match(r'^(.+?)\s*\(([^)]+)\).*$', food_and_nutrition)
            if paren_match:
                food_name = paren_match.group(1).strip()
                nutrition_part = paren_match.group(2).strip()
                
                item["name"] = food_name
                item["description"] = f"From {restaurant}"
                
                # Parse nutrition from parentheses (comma-separated)
                nutrition_items = [n.strip() for n in nutrition_part.split(',')]
                for nutrition_item in nutrition_items:
                    # Extract calories
                    cal_match = re.search(r'(\d+)\s*kcal', nutrition_item, re.IGNORECASE)
                    if cal_match:
                        item["calories"] = int(cal_match.group(1))
                        continue
                    
                    # Extract protein (look for "Xg protein" or just "Xg" after other nutrients)
                    protein_match = re.search(r'(\d+(?:\.\d+)?)\s*g\s*protein', nutrition_item, re.IGNORECASE)
                    if protein_match:
                        item["protein"] = float(protein_match.group(1))
                        continue
                
                return item
        
        # Check for format with parentheses only: "Food Name (nutrition info)"
        elif '(' in item_text and ')' in item_text:
            paren_match = re.match(r'^(.+?)\s*\(([^)]+)\).*$', item_text)
            if paren_match:
                name_part = paren_match.group(1).strip()
                nutrition_part = paren_match.group(2).strip()
                
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
        
        # Check for format with colon only: "Restaurant: Food Name"
        elif ':' in item_text:
            parts = item_text.split(':', 1)
            restaurant = parts[0].strip()
            food_name = parts[1].strip()
            
            item["name"] = food_name
            item["description"] = f"From {restaurant}"
        
        else:
            # Just the food name
            item["name"] = item_text.strip()
        
        # Return the item if we have at least a name
        if item["name"]:
            return item
        else:
            return None
            
    except Exception as e:
        logger.error(f"Error parsing inline food item '{item_text}': {e}")
        return {"name": item_text, "calories": None, "protein": None, "description": ""}

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
    """
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
    
    # Add specific instructions to use the tools
    if 'breakfast' in needed_meals and 'lunch' in needed_meals and 'dinner' in needed_meals:
        prompt += "\n\nPlease use the `build_daily_meal_plan` tool to create a comprehensive meal plan that meets these requirements. Make sure to include specific food items from Duke dining locations with nutritional information."
    else:
        prompt += "\n\nPlease use the `create_meal` tool for each requested meal type to provide specific food recommendations from Duke dining locations."
    
    prompt += "\n\nFormat your response clearly by meal type (breakfast, lunch, dinner) and include restaurant names and nutritional information for each food item."
    
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
            
            # Extract the data from the agent response
            if hasattr(agent_response, 'output'):
                agent_text = str(agent_response.output)
            elif hasattr(agent_response, 'data'):
                agent_text = str(agent_response.data)
            else:
                agent_text = str(agent_response)
                
            logger.info(f"Agent text for parsing: {agent_text}")
            
        except Exception as e:
            logger.error(f"Error calling agent: {e}")
            logger.error(f"Traceback: {traceback.format_exc()}")
            return jsonify({
                "error": "Failed to call nutrition agent",
                "details": str(e)
            }), 500
        
        # Parse the agent response to structured data
        meal_plan = parse_agent_response(agent_text)
        
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
        
        return jsonify(meal_plan)
        
    except Exception as e:
        logger.error(f"Error generating meal plan: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        return jsonify({
            "error": "Failed to generate meal plan",
            "details": str(e)
        }), 500

@app.route('/api/health', methods=['GET'])
def health_check():
    """
    Simple health check endpoint.
    """
    return jsonify({"status": "healthy", "message": "Duke Eats API is running"})

# Parser debugging complete

@app.route('/')
def serve_index():
    """
    Serve the main HTML file.
    """
    return send_from_directory('.', 'index.html')

@app.route('/<path:filename>')
def serve_static_files(filename):
    """
    Serve static files (JS, CSS, etc.)
    """
    return send_from_directory('.', filename)

if __name__ == '__main__':
    # Run the development server
    app.run(debug=True, host='0.0.0.0', port=3000)
