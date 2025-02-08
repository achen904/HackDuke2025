import requests
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import sqlite3
import time
import sys
import subprocess

def install_missing_packages():
    packages = ["requests", "beautifulsoup4", "selenium", "sqlite3"]
    for package in packages:
        try:
            __import__(package)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def scrape_duke_nutrition():
    url = "https://netnutrition.cbord.com/nn-prod/Duke"
    driver = webdriver.Safari()
    driver.get(url)
    
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.TAG_NAME, "body"))  # Wait for page to load
        )
        print("Page loaded successfully")
    except Exception as e:
        print("Error loading page elements:", e)
        driver.quit()
        return None
    
    food_items = []
    try:
        page_source = driver.page_source
        soup = BeautifulSoup(page_source, "html.parser")
        menu_items = soup.find_all("div", class_="menu-item-class")  # Update based on actual class
        
        for item in menu_items:
            name = item.find("h3").text.strip() if item.find("h3") else "Unknown"
            calories = item.find("span", class_="calories").text.strip() if item.find("span", class_="calories") else "0"
            protein = item.find("span", class_="protein").text.strip() if item.find("span", class_="protein") else "0"
            carbs = item.find("span", class_="carbs").text.strip() if item.find("span", class_="carbs") else "0"
            
            food_items.append({
                "name": name,
                "calories": calories,
                "protein": protein,
                "carbs": carbs
            })
        print(f"Scraped {len(food_items)} items successfully.")
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
    print("Data successfully stored in database.")

if __name__ == "__main__":
    install_missing_packages()
    food_data = scrape_duke_nutrition()
    if food_data:
        store_data_in_db(food_data)
    else:
        print("No data scraped.")
