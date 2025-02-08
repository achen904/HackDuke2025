import random
import os
from dotenv import load_dotenv
from pydantic_ai import Agent
import openai
from pydantic_ai.models.openai import OpenAIModel


load_dotenv()

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
model = OpenAIModel('gpt-4o-mini')
agent = Agent(model, system_prompt=("Respond in one sentence"))


@agent.tool_plain  
def get_dietary_restrictions() -> str:
    return input("What are your food allergens?")

# First run
result1 = agent.run_sync('Give me a meal plan')
print(result1.data)
#> Albert Einstein was a German-born theoretical physicist.

# Second run, passing previous messages
# result2 = agent.run_sync(
#     'What was his most famous equation?',
#     message_history=result1.new_messages(),  
# )
# print(result2.data)
#> Albert Einstein's most famous equation is (E = mc^2).

