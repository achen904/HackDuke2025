import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sqlite3
import time

def scrape_duke_nutrition():
    url = "https://netnutrition.cbord.com/nn-prod/Duke"
    driver = webdriver.Chrome()
    driver.get(url)
    
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CLASS_NAME, "menu-item-class"))  # Adjust this selector
        )
    except Exception as e:
        print("Error loading page elements:", e)
        driver.quit()
        return None
    
    food_items = []
    try:
        menu_items = driver.find_elements(By.CLASS_NAME, "menu-item-class")  # Adjust based on site structure
        for item in menu_items:
            name = item.find_element(By.TAG_NAME, "h3").text.strip()
            calories = item.find_element(By.CLASS_NAME, "calories").text.strip()
            protein = item.find_element(By.CLASS_NAME, "protein").text.strip()
            carbs = item.find_element(By.CLASS_NAME, "carbs").text.strip()
            
            food_items.append({
                "name": name,
                "calories": calories,
                "protein": protein,
                "carbs": carbs
            })
    except Exception as e:
        print("Error extracting food items:", e)
    
    driver.quit()
    return food_items

def store_data_in_db(food_items):
    conn = sqlite3.connect("duke_nutrition.db")
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS menu (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            calories INTEGER,
            protein INTEGER,
            carbs INTEGER
        )
    ''')
    
    for item in food_items:
        cursor.execute('''
            INSERT INTO menu (name, calories, protein, carbs)
            VALUES (?, ?, ?, ?)
        ''', (item["name"], item["calories"], item["protein"], item["carbs"]))
    
    conn.commit()
    conn.close()

if __name__ == "__main__":
    food_data = scrape_duke_nutrition()
    if food_data:
        store_data_in_db(food_data)
        print("Data successfully stored in database.")
    else:
        print("No data scraped.")
