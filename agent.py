from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
import os
import sqlite3
from sentence_transformers import SentenceTransformer
import faiss;
import numpy as np;

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
def rank_foods(ctx: RunContext[str]) -> str:
    # Connect to the SQLite database
    conn = sqlite3.connect('dummy1.db')
    cursor = conn.cursor()

    nutrients = ["calories", "total_fat", "saturated_fat", "trans_fat", "cholesterol", "sodium", "total_carbs", "dietary_fiber", "total_sugars", "added_sugars", "protein", "calcium", "iron", "potassium"]

    for nutrient in nutrients:
        title = nutrient + "_rank"
        addColumn =  f"ALTER TABLE items ADD COLUMN {title}"
        cursor.execute(addColumn)
        cursor.executescript(f"""
        WITH ranked_product AS (
                SELECT {nutrient}, 
            RANK() OVER (ORDER BY {nutrient} DESC) AS price_rank,
            COUNT(*) OVER () AS total_rows 
            FROM items
            )
            UPDATE items
            SET {title} = CASE
                WHEN ranked_product.price_rank <= ranked_product.total_rows / 3 THEN 'High'
                WHEN ranked_product.price_rank <= 2 * ranked_product.total_rows / 3 THEN 'Medium'
                ELSE 'Low'
            END
            FROM ranked_product
            WHERE items.{nutrient} = ranked_product.{nutrient};
        """)

@agent.tool
def create_meal(ctx: RunContext[str]) -> str:
    conn = sqlite3.connect('dummy1.db')
    cursor = conn.cursor()

    # Fetch data from Net Nutrition
    cursor.execute("SELECT name, calories_rank, total_fat_rank, saturated_fat_rank, trans_fat_rank, cholesterol_rank, sodium_rank, total_carbs_rank, dietary_fiber_rank, total_sugars_rank, added_sugars_rank, protein_rank, calcium_rank, iron_rank, potassium_rank FROM items")
    data = cursor.fetchall()

    # Close the connection
    conn.close()

    # Organize the data for use
    food_names = [entry[0] for entry in data]
    nutritional_info = [entry[1:] for entry in data]  # Excluding food name


    # Load pre-trained sentence embedding model
    model = SentenceTransformer('paraphrase-MiniLM-L6-v2')

    food_descriptions = [f"{cal[0]} Calories, {cal[1]} Total Fat, {cal[2]} Saturated Fat, {cal[3]} Trans-Fat, {cal[4]} Cholesterol, {cal[5]} Sodium, {cal[6]} Total Carbs, {cal[7]} Dietary Fiber, {cal[8]} Total Sugars, {cal[9]} Added Sugars, {cal[10]} Protein, {cal[11]} Calcium, {cal[12]} Iron, {cal[13]} Potassium" 
                        for cal in nutritional_info]

    # Generate embeddings
    embeddings = model.encode(food_descriptions)

    # Convert embeddings to numpy array
    embeddings_np = np.array(embeddings).astype('float32')

    faiss.normalize_L2(embeddings_np)

    # Create a FAISS index (using Inner Product distance metric)
    index = faiss.IndexFlatIP(embeddings_np.shape[1])
    index.add(embeddings_np)

    user_preferences = "High protein"
    num_meals =3

    user_pref_embedding = model.encode([user_preferences]).astype('float32')

    # Find top food items from FAISS
    D, I = index.search(user_pref_embedding, num_meals)

    meal_plan = []
    for idx in I[0]:
        food_item = food_names[idx]
        nutrition = nutritional_info[idx]
        meal_plan.append({
            'food': food_item,
            'calories': nutrition[0],
            'total fat': nutrition[1],
            'saturated fat': nutrition[2],
            'trans-fat': nutrition[3],
            'cholesterol': nutrition[4],
            'sodium': nutrition[5],
            'total carbs': nutrition[6],
            'dietary fiber': nutrition[7],
            'total sugars': nutrition[8],
            'added sugars': nutrition[9],
            'protein': nutrition[10],
            'calcium': nutrition[11],
            'iron': nutrition[12],
            'potassium': nutrition[13],
        })

    return (" ").join(meal_plan)


@agent.tool
def delete_database(db_file):
    os.remove(db_file)  

@agent.tool
def create_database(db_file):
    sqlite3.connect(db_file)



@agent.tool  
def get_allergens(ctx: RunContext[str]) -> str:
    """Get the player's allergens."""
    return ctx.deps

def main():
    meal_plan = agent.run_sync("What should I eat today", deps='No Meat')  
    print(meal_plan.data)
    