import time
import sqlite3
import subprocess
import sys
import os
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

def install_missing_packages():
    packages = ["playwright", "beautifulsoup4"]
    for package in packages:
        try:
            __import__(package)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def scrape_restaurant_names():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        menu_url = "https://netnutrition.cbord.com/nn-prod/Duke"
        page.goto(menu_url)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_load_state("networkidle")
        
        try:
            page.wait_for_selector("#cbo_nn_unitDataList .col-12 .card.unit", timeout=20000)
        except Exception as e:
            print("Error: Could not find restaurant elements. Inspecting HTML...")
            print(page.content())
            return []
        
        html_content = page.content()
        soup = BeautifulSoup(html_content, "html.parser")
        
        restaurants = []
        for card in soup.select("#cbo_nn_unitDataList .col-12 .card.unit"):
            name_element = card.select_one("a")
            status_element = card.select_one(".badge")
            
            if name_element and status_element:
                name = name_element.text.strip()
                status = status_element.text.strip()
                restaurants.append({"name": name, "status": status})
        
        print("Found Restaurants:", restaurants)
        
        browser.close()
        return restaurants

def store_restaurants_in_db(restaurants):
    conn = sqlite3.connect("duke_nutrition.db")
    cursor = conn.cursor()
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS restaurants (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            status TEXT
        )
    ''')
    
    for restaurant in restaurants:
        cursor.execute('''
            INSERT INTO restaurants (name, status) VALUES (?, ?)
        ''', (restaurant["name"], restaurant["status"]))
    
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
