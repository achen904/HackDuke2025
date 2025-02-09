import sqlite3
from sentence_transformers import SentenceTransformer
import faiss;
import numpy as np;


# Connect to the SQLite database
conn = sqlite3.connect('duke_nutrition.db')
cursor = conn.cursor()

# Fetch data from food table (replace with your actual table and columns)
cursor.execute("SELECT name, calories, total_fat, saturated_fat, trans_fat, cholesterol, sodium, total_carbs, dietary_fiber, total_sugars, added_sugars, protein, calcium, iron, potassium FROM items")
data = cursor.fetchall()

# Close the connection
conn.close()

# Organize the data for use
food_names = [entry[0] for entry in data]
nutritional_info = [entry[1:] for entry in data]  # Excluding food name


# Load pre-trained sentence embedding model
model = SentenceTransformer('paraphrase-MiniLM-L6-v2')

# Combine food name with nutritional information for more context
food_descriptions = [f"{name} - Calories: {cal}, Total Fat: {tf}, Saturated Fat: {sf}, Trans-Fat: {trf}, Cholesterol: {ch}, Sodium: {sodium}, Total Carbs: {tc}, Dietary Fiber:{df}, Total Sugars:{ts}, Added Sugars:{ass}, Protein:{prot}, Calcium:{calc}, Iron:{iron}, Potassium:{pot}" 
                     for name, (cal, tf, sf, trf, ch, sodium, tc, df, ts, ass, prot, calc, iron, pot) in zip(food_names, nutritional_info)]

# Generate embeddings
embeddings = model.encode(food_descriptions)

# Convert embeddings to numpy array
embeddings_np = np.array(embeddings).astype('float32')

# Create a FAISS index (using L2 distance metric)
index = faiss.IndexFlatL2(embeddings_np.shape[1])
index.add(embeddings_np)

# User preferences or dietary restrictions
user_preference = "high protein, low carb"

# Convert the user preference into an embedding
user_preference_embedding = model.encode([user_preference]).astype('float32')

# Search for food items that match the user preference (top 5 results)
D, I = index.search(user_preference_embedding, 5)

# Retrieve matching food names and nutritional info
recommended_foods = [(food_names[i], nutritional_info[i]) for i in I[0]]

# Output the recommended foods for the meal plan
print("Recommended Foods:", recommended_foods)


def create_meal_plan(user_preferences, num_meals=3):
    # Convert user preferences to embedding
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
            'protein': nutrition[1],
            'fat': nutrition[2],
            'carbs': nutrition[3]
        })

    return meal_plan

# Example user input: high-protein, low-carb diet
user_input = "high protein, low carb"
meal_plan = create_meal_plan(user_input)

# Output the meal plan
print("Your meal plan:")
for meal in meal_plan:
    print(meal)