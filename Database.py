import sqlite3

def store_nutrition(items):
    conn = sqlite3.connect("duke_nutrition.db")
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
            INSERT INTO restaurants (name, calories, total_fat, saturated_fat, trans_fat, cholesterol, sodium, total_carbs, dietary_fiber, total_sugars, added_sugar, protein, calcium, iron, potassium) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (food["name"], food["calories"], food["total_fat"], food["saturated_fat"], food["trans_fat"], food["cholesterol"], food["sodium"], food["total_carbs"], food["dietary_fiber"], food["total_sugars"], food["added_sugars"], food["protein"], food["calcium"], food["iron"], food["potassium"]))
    
    conn.commit()
    conn.close()
    print("Restaurant data successfully stored in database.")

if __name__ == "__main__":
    install_missing_packages()
    restaurant_data = scrape_restaurant_names()
    if restaurant_data:
        store_restaurants_in_db(restaurant_data)
    else:
        print("No restaurants scraped.")
