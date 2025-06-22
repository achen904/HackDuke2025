from dotenv import load_dotenv
from pydantic_ai import Agent, RunContext
import os
import sqlite3
from sentence_transformers import SentenceTransformer
import faiss;
import numpy as np;
import openai
from typing import Optional, Dict, List

load_dotenv()

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

When the user requests a meal suggestion or plan, first call the `rank_foods` tool (if the *_rank columns are missing)
and then ALWAYS call `create_meal` with:
  preferences: a concise description of the user's nutritional goals or keywords taken from their request,
  num_meals: how many food items to return (default 3).

After receiving the tool result, respond to the user using ONLY the food names in that result; do not invent or add items that are not present.

If the user asks general nutrition questions not requiring a specific meal recommendation, answer normally.""",
)

@agent.tool
def rank_foods(ctx: RunContext[str]) -> str:
    # Connect to the SQLite database
    conn = sqlite3.connect('duke_nutrition.db')
    cursor = conn.cursor()

    nutrients = [
        "calories",
        "total_fat",
        "saturated_fat",
        "trans_fat",
        "cholesterol",
        "sodium",
        "total_carbs",
        "dietary_fiber",
        "total_sugars",
        "added_sugars",
        "protein",
        "calcium",
        "iron",
        "potassium",
    ]

    # Get existing columns to avoid duplicate ALTERs
    existing_cols = {row[1] for row in cursor.execute("PRAGMA table_info(items)")}

    for nutrient in nutrients:
        title = f"{nutrient}_rank"

        # Add the column only if it does not exist already
        if title not in existing_cols:
            cursor.execute(f"ALTER TABLE items ADD COLUMN {title}")

        # (Re)calculate the ranking values – safe even if column already existed
        cursor.executescript(
            f"""
            WITH ranked_product AS (
                SELECT {nutrient},
                       RANK() OVER (ORDER BY {nutrient} DESC) AS price_rank,
                       COUNT(*) OVER ()                       AS total_rows
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
            """
        )

    conn.commit()
    conn.close()

@agent.tool
def create_meal(
    ctx: RunContext[str],
    preferences: str,
    num_meals: int = 3,
    allowed_foods: Optional[List[str]] = None,
) -> str:
    conn = sqlite3.connect("duke_nutrition.db")
    cursor = conn.cursor()

    # Fetch restaurant name along with other data
    cursor.execute(
        """
        SELECT name, restaurant,  -- Added restaurant column here
               calories, total_fat, saturated_fat, trans_fat, cholesterol, sodium, 
               total_carbs, dietary_fiber, total_sugars, added_sugars, protein, 
               calcium, iron, potassium,
               calories_rank, total_fat_rank, saturated_fat_rank, trans_fat_rank, 
               cholesterol_rank, sodium_rank, total_carbs_rank, dietary_fiber_rank, 
               total_sugars_rank, added_sugars_rank, protein_rank, calcium_rank, 
               iron_rank, potassium_rank
        FROM items
        """
    )
    data = cursor.fetchall()

    # If a subset of food names is provided, filter rows early
    if allowed_foods:
        allowed_set = set(f.lower() for f in allowed_foods)
        # Assuming name is at index 0
        data = [row for row in data if row[0].lower() in allowed_set]

    conn.close()

    food_names = []
    food_restaurants = [] # New list to store restaurants
    numeric_info = []     # list of tuples (14 numeric)
    rank_info = []        # list of tuples (14 rank strings)

    for row in data:
        food_names.append(row[0])
        food_restaurants.append(row[1]) # Store restaurant (it's at index 1 now)
        numeric_info.append(row[2:16])  # Adjust indices: numeric data now starts at index 2
        rank_info.append(row[16:])      # Adjust indices: rank data now starts at index 16


    # Load pre-trained sentence embedding model
    # Ensure you have sentence-transformers installed: pip install sentence-transformers
    model = SentenceTransformer("paraphrase-MiniLM-L6-v2")

    # Build textual description from ranks for embedding similarity
    food_descriptions = [
        f"{r[0]} Calories, {r[1]} Total Fat, {r[2]} Saturated Fat, {r[3]} Trans-Fat, {r[4]} Cholesterol, {r[5]} Sodium, {r[6]} Total Carbs, {r[7]} Dietary Fiber, {r[8]} Total Sugars, {r[9]} Added Sugars, {r[10]} Protein, {r[11]} Calcium, {r[12]} Iron, {r[13]} Potassium"
        for r in rank_info
    ]

    # Generate embeddings
    embeddings = model.encode(food_descriptions)

    # Convert embeddings to numpy array
    embeddings_np = np.array(embeddings).astype('float32')

    if embeddings_np.shape[0] == 0: # No food items match, possibly after filtering
        return str([]) # Return empty list as string

    faiss.normalize_L2(embeddings_np)

    # Create a FAISS index (using Inner Product distance metric)
    index = faiss.IndexFlatIP(embeddings_np.shape[1])
    index.add(embeddings_np)

    user_pref_embedding = model.encode([preferences]).astype('float32')
    faiss.normalize_L2(user_pref_embedding)


    # Find top food items from FAISS
    # Ensure num_meals is not greater than the number of items in the index
    k = min(num_meals, embeddings_np.shape[0])
    if k == 0:
        return str([])
        
    D, I = index.search(user_pref_embedding, k)

    meal_plan = []
    for i in range(k): # Iterate up to k (number of actual results found)
        idx = I[0][i]
        if idx < 0 or idx >= len(food_names): # faiss can return -1 if not enough neighbors
            continue

        food_item_name = food_names[idx]
        food_item_restaurant = food_restaurants[idx] # Get restaurant
        numbers = numeric_info[idx]
        
        meal_plan.append({
            "food": food_item_name,
            "restaurant": food_item_restaurant, # Include restaurant
            "calories": numbers[0],
            "total_fat": numbers[1],
            "saturated_fat": numbers[2],
            "trans_fat": numbers[3],
            "cholesterol": numbers[4],
            "sodium": numbers[5],
            "total_carbs": numbers[6],
            "dietary_fiber": numbers[7],
            "total_sugars": numbers[8],
            "added_sugars": numbers[9],
            "protein": numbers[10],
            "calcium": numbers[11],
            "iron": numbers[12],
            "potassium": numbers[13],
        })

    return str(meal_plan) 

@agent.tool
def delete_database(ctx: RunContext[str], db_file: str = "duke_nutrition.db") -> str:
    """Delete the specified SQLite database file.

    Parameters
    ----------
    db_file : str
        Path to the SQLite database file. Defaults to "duke_nutrition.db".
    """
    try:
        os.remove(db_file)
        return f"Deleted database file: {db_file}"
    except FileNotFoundError:
        return f"Database file not found: {db_file}"
    except Exception as e:
        return f"Error deleting database file: {e}"

@agent.tool
def create_database(ctx: RunContext[str], db_file: str = "duke_nutrition.db") -> str:
    """Create a new SQLite database file (or open if it exists)."""
    try:
        sqlite3.connect(db_file)
        return f"Database created or opened successfully: {db_file}"
    except Exception as e:
        return f"Error creating database: {e}"

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
def clear_items(ctx: RunContext[str], db_file: str = "duke_nutrition.db") -> str:
    """Delete all rows from the `items` table while keeping the database file intact.

    This is useful when you want to preserve the schema but repopulate the table
    with fresh data using the scraper.
    """
    try:
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()
        cur.execute("DELETE FROM items")
        deleted = cur.rowcount  # -1 means undetermined for SQLite
        conn.commit()
        conn.close()
        msg = (
            f"Cleared {deleted if deleted != -1 else 'all'} rows from 'items' table in {db_file}."
        )
        return msg
    except sqlite3.OperationalError as e:
        # Likely the table does not exist yet
        return f"Error: {e}. Make sure the 'items' table exists before clearing."
    except Exception as e:
        return f"Unexpected error clearing items: {e}"

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