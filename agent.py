import random
from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
import os

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


dice_result = agent.run_sync("What should I eat today", deps='No Meat')  
print(dice_result.data)