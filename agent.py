import random
from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
import os
import sqlite3

load_dotenv()



OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")

agent = Agent(
    'openai:gpt-4o-mini',  
    deps_type=str,  
    system_prompt=(
        "You are a diet and nutrition expert. Based off of what is available to eat, please create a meal plan that considers dietary restrictions"
    ),
)


@agent.tool 
def get_meal(ctx: RunContext[str]) -> str:
    return "Chicken Parmesan, Steak, Salad, Fruit"


@agent.tool  
def get_allergens(ctx: RunContext[str]) -> str:
    """Get the player's allergens."""
    return ctx.deps

def main():
    dice_result = agent.run_sync("What should I eat today", deps='No Meat')  
    print(dice_result.data)
    
    conn = sqlite3.connect('dummy.db')
    cursor = conn.cursor()

    # Fetch data from Net Nutrition
    cursor.execute("SELECT name, calories, total_fat, saturated_fat, trans_fat, cholesterol, sodium, total_carbs, dietary_fiber, total_sugars, added_sugars, protein, calcium, iron, potassium FROM items")
    data = cursor.fetchall()

    # Close the connection
    conn.close()

    # Organize the data for use
    food_names = [entry[0] for entry in data]
    nutritional_info = [entry[1:] for entry in data]  # Excluding food name