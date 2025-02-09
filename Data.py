import sqlite3

def store_nutrition(items):
    conn = sqlite3.connect("dummy2.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            calories INTEGER,
            total_fat INTEGER,
            saturated_fat INTEGER,
            trans_fat INTEGER,
            cholesterol INTEGER,
            sodium INTEGER,
            total_carbs INTEGER,
            dietary_fiber INTEGER,
            total_sugars INTEGER,
            added_sugars INTEGER,
            protein INTEGER,
            calcium INTEGER,
            iron INTEGER,
            potassium INTEGER
            
        )
    ''')
    
    for food in items:
        print(food)
        cursor.execute('''
            INSERT INTO items (name, calories, total_fat, saturated_fat, trans_fat, cholesterol, sodium, total_carbs, dietary_fiber, total_sugars, added_sugars, protein, calcium, iron, potassium) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (food["name"], food["calories"], food["total_fat"], food["saturated_fat"], food["trans_fat"], food["cholesterol"], food["sodium"], food["total_carbs"], food["dietary_fiber"], food["total_sugars"], food["added_sugars"], food["protein"], food["calcium"], food["iron"], food["potassium"]))
    
    conn.commit()
    conn.close()
    print("Item data successfully stored in database.")

def main():
    items = [{"name": "Roasted Garlic Rubbed Chicken", "calories": 390, "total_fat": 25, "saturated_fat": 6, "trans_fat": 0, "cholesterol": 125, "sodium": 980, "total_carbs": 1, "dietary_fiber": 0, "total_sugars": 0, "added_sugars": 0, "protein": 39, "calcium": 39, "iron": 2, "potassium": 780},
             {"name": "Hush Puppies", "calories": 230, "total_fat": 11, "saturated_fat": 2, "trans_fat": 0, "cholesterol": 10, "sodium": 430, "total_carbs": 28, "dietary_fiber": 3, "total_sugars": 6, "added_sugars": 0, "protein": 1, "calcium": 89, "iron": 1, "potassium": 0},
             {"name": "Roasted Zucchini", "calories": 60, "total_fat": 6, "saturated_fat": 1, "trans_fat": 0, "cholesterol": 0, "sodium": 630, "total_carbs": 3, "dietary_fiber": 1, "total_sugars": 2, "added_sugars": 0, "protein": 1, "calcium": 19, "iron": 0, "potassium": 280}]
    store_nutrition(items)

if __name__ == "__main__":
    main()
        