import sqlite3
from sentence_transformers import SentenceTransformer
import faiss;
import numpy as np;


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