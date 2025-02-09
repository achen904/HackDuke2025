import sqlite3

def store_nutrition(items):
    conn = sqlite3.connect("duke_nutrition.db")
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
            id DOUBLE PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            calories DOUBLE,
            total_fat DOUBLE,
            saturated_fat DOUBLE,
            trans_fat DOUBLE,
            cholesterol DOUBLE,
            sodium DOUBLE,
            total_carbs DOUBLE,
            dietary_fiber DOUBLE,
            total_sugars DOUBLE,
            added_sugars DOUBLE,
            protein DOUBLE,
            calcium DOUBLE,
            iron DOUBLE,
            potassium DOUBLE
        )
    ''')
    
    for food in items:
        print(food)
        cursor.execute('''
            INSERT INTO items (name, calories, total_fat, saturated_fat, trans_fat, cholesterol, sodium, total_carbs, dietary_fiber, total_sugars, added_sugar, protein, calcium, iron, potassium) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (food["name"], food["calories"], food["total_fat"], food["saturated_fat"], food["trans_fat"], food["cholesterol"], food["sodium"], food["total_carbs"], food["dietary_fiber"], food["total_sugars"], food["added_sugars"], food["protein"], food["calcium"], food["iron"], food["potassium"]))
    
    conn.commit()
    conn.close()
    print("Item data successfully stored in database.")

if __name__ == "__main__":
    install_missing_packages()
    restaurant_data = scrape_restaurant_names()
    if restaurant_data:
        store_restaurants_in_db(restaurant_data)
    else:
        print("No restaurants scraped.")
