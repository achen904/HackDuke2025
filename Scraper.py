import time
import subprocess
import sys
import sqlite3
from playwright.sync_api import sync_playwright

def install_missing_packages():
    """Ensure required packages are installed."""
    packages = ["playwright"]
    for package in packages:
        try:
            __import__(package)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def setup_database():
    """Set up SQLite database to store meals, locations, food, and nutrition data."""
    conn = sqlite3.connect("duke_nutrition.db")
    cursor = conn.cursor()
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS meals (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT UNIQUE
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS locations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            meal_id INTEGER,
            name TEXT,
            FOREIGN KEY(meal_id) REFERENCES meals(id)
        )
    """)
    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS food_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location_id INTEGER,
            name TEXT UNIQUE,
            nutrition_info TEXT,
            FOREIGN KEY(location_id) REFERENCES locations(id)
        )
    """)

    conn.commit()
    conn.close()

def save_to_database(meal, location, food_name, nutrition_info):
    """Save extracted data into SQLite database."""
    conn = sqlite3.connect("duke_nutrition.db")
    cursor = conn.cursor()

    # Insert meal if not exists
    cursor.execute("INSERT OR IGNORE INTO meals (name) VALUES (?)", (meal,))
    cursor.execute("SELECT id FROM meals WHERE name=?", (meal,))
    meal_id = cursor.fetchone()[0]

    # Insert location if not exists
    cursor.execute("INSERT OR IGNORE INTO locations (meal_id, name) VALUES (?, ?)", (meal_id, location))
    cursor.execute("SELECT id FROM locations WHERE meal_id=? AND name=?", (meal_id, location))
    location_id = cursor.fetchone()[0]

    # Insert food item
    cursor.execute("""
        INSERT INTO food_items (location_id, name, nutrition_info)
        VALUES (?, ?, ?)
    """, (location_id, food_name, nutrition_info))

    conn.commit()
    conn.close()

def scrape_marketplace_data():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        context = browser.new_context(viewport={"width": 1280, "height": 800})
        page = context.new_page()

        page.goto("https://netnutrition.cbord.com/nn-prod/Duke", wait_until="networkidle")

        # Close any pop-ups
        try:
            page.click("button.close >> visible=true", timeout=5000)
        except:
            pass

        # Enter Marketplace
        page.click("a.text-white:has-text('Marketplace') >> visible=true")
        page.wait_for_load_state("networkidle")

        # Meal XPaths (processed in order)
        meal_xpaths = [
            ("Saturday Brunch", "(//a[contains(@class,'cbo_nn_menuLink') and contains(text(),'Brunch')])[1]"),
            ("Saturday Dinner", "(//a[contains(@class,'cbo_nn_menuLink') and contains(text(),'Dinner')])[1]"),
            ("Sunday Brunch", "(//a[contains(@class,'cbo_nn_menuLink') and contains(text(),'Brunch')])[2]"),
            ("Sunday Dinner", "(//a[contains(@class,'cbo_nn_menuLink') and contains(text(),'Dinner')])[2]"),
            ("Monday Breakfast", "(//a[contains(@class,'cbo_nn_menuLink') and contains(text(),'Breakfast')])[1]"),
            ("Monday Lunch", "(//a[contains(@class,'cbo_nn_menuLink') and contains(text(),'Lunch')])[1]"),
            ("Monday Dinner", "(//a[contains(@class,'cbo_nn_menuLink') and contains(text(),'Dinner')])[3]"),
        ]

        # Specific location XPaths
        location_xpaths = [
            f"/html/body/div/div[2]/form/div/div[2]/main/div[5]/section/div[4]/table/tbody/tr[{i}]/td/div"
            for i in [1, 4, 9, 18, 23, 29, 33, 38, 41, 49, 53, 59, 62, 72, 76, 80, 84, 106, 112, 120, 125, 135, 138]
        ]

        # Back Button XPath
        back_button_xpath = "/html/body/div[1]/div[2]/form/div/div[2]/main/div[5]/section/div[1]/nav/a[1]"

        for meal_name, meal_xpath in meal_xpaths:
            print(f"\n📌 Processing {meal_name}...")

            meal_element = page.locator(f"xpath={meal_xpath}").first
            meal_element.click(force=True)
            page.wait_for_load_state("networkidle")
            time.sleep(2)

            visited_foods = set()

            for location_xpath in location_xpaths:
                try:
                    location_element = page.locator(f"xpath={location_xpath}")
                    location_element.click(force=True)
                    page.wait_for_load_state("networkidle")
                    time.sleep(1)

                    food_elements = page.locator("xpath=//a[contains(@class,'cbo_nn_itemHover')]").all()
                    for food_element in food_elements:
                        food_name = food_element.text_content().strip()
                        if food_name not in visited_foods:
                            visited_foods.add(food_name)
                            food_element.scroll_into_view_if_needed()
                            food_element.click(force=True)

                            page.wait_for_load_state("networkidle")
                            time.sleep(1)

                            # Extract nutritional facts
                            nutrition_info = extract_nutrition_info(page)
                            
                            print(f"    🍽 {food_name} - {nutrition_info}")
                            save_to_database(meal_name, location_element.text_content().strip(), food_name, nutrition_info)

                            # Close the nutrition popup
                            try:
                                close_button = page.locator("xpath=//button[@id='btn_nn_nutrition_close']")
                                if close_button.is_visible():
                                    close_button.click()
                                    page.wait_for_load_state("networkidle")
                                    time.sleep(1)
                            except:
                                pass

                except Exception as e:
                    print(f"⚠️ Skipping location due to error: {e}")

            # Click back button after processing all food in the location
            try:
                back_button = page.locator(f"xpath={back_button_xpath}")
                back_button.click(force=True)
                page.wait_for_load_state("networkidle")
                time.sleep(2)
            except:
                print(f"⚠️ Could not find back button, returning to main menu.")
                page.goto("https://netnutrition.cbord.com/nn-prod/Duke")
                page.wait_for_load_state("networkidle")

        browser.close()

def extract_nutrition_info(page):
    """Extracts nutrition information from the popup window."""
    try:
        page.wait_for_selector("text=Nutrition Information", state='visible', timeout=5000)
        nutrition_info = page.evaluate("""
            () => {
                let elements = document.querySelectorAll("div#nutritionLabel div");
                return Array.from(elements).map(e => e.textContent.trim()).join("\\n");
            }
        """)
        return nutrition_info if nutrition_info else "No nutrition info available"
    except:
        return "Nutrition info extraction failed"

if __name__ == "__main__":
    install_missing_packages()
    setup_database()
    scrape_marketplace_data()
