import os
import re
import sqlite3
import subprocess
import sys
import time
from typing import Dict, List, Tuple

import requests
from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright

# -------------------------------------------------------------
# CONFIGURATION
# -------------------------------------------------------------
BASE_URL = "https://netnutrition.cbord.com/nn-prod/Duke"
# Name of the dining unit as it appears on the first page (e.g. "Marketplace", "Ginger + Soy")
UNIT_NAME = "The Skillet"

NUTRITION_ENDPOINT = (
    BASE_URL + "/Nutrition/GetItemNutrition?itemID={item_id}&type=html"
)
DB_PATH = "duke_nutrition.db"

# Mapping from NetNutrition labels (lower-case) to DB column names
LABEL_MAP = {
    "calories": "calories",
    "total fat": "total_fat",
    "saturated fat": "saturated_fat",
    "trans fat": "trans_fat",
    "cholesterol": "cholesterol",
    "sodium": "sodium",
    "total carbohydrate": "total_carbs",
    "total carbs": "total_carbs",  # fallback wording
    "dietary fiber": "dietary_fiber",
    "total sugars": "total_sugars",
    "added sugars": "added_sugars",
    "protein": "protein",
    "calcium": "calcium",
    "iron": "iron",
    "potassium": "potassium",
}

# Order of columns for INSERT operations
DB_COLUMNS = [
    "name",
    "restaurant",
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


# -------------------------------------------------------------
# UTILITY FUNCTIONS
# -------------------------------------------------------------

def ensure_dependencies():
    """Ensure Playwright and browser binaries are installed."""
    try:
        import playwright  # noqa: F401
    except ImportError:
        subprocess.check_call([sys.executable, "-m", "pip", "install", "playwright", "requests", "beautifulsoup4"])
    # Make sure browsers are installed (only once)
    subprocess.run([sys.executable, "-m", "playwright", "install", "chromium"], check=False, stdout=subprocess.PIPE)


def setup_database():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            restaurant TEXT,
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
            potassium INTEGER,
            UNIQUE(name, restaurant)
        )
        """
    )
    conn.commit()
    conn.close()


def parse_nutrition_html(html: str) -> Dict[str, int]:
    """Parse NetNutrition HTML snippet into a dict keyed by DB column names.
    
    The HTML structure looks like:
    - Calories: in a div with class "inline-div-right bold-text font-22"
    - Other nutrients: in spans like "Total Fat" followed by "&nbsp;1.5g"
    """
    soup = BeautifulSoup(html, "html.parser")
    nutrition: Dict[str, int] = {key: 0 for key in LABEL_MAP.values()}

    # Extract calories from the special calories section
    calories_div = soup.select_one("div.inline-div-right.bold-text.font-22")
    if calories_div:
        calories_text = calories_div.get_text(strip=True)
        calories_match = re.search(r"(\d+)", calories_text)
        if calories_match:
            nutrition["calories"] = int(calories_match.group(1))

    # Extract other nutrients from span patterns
    # Look for patterns like <span class="bold-text">Total Fat</span><span>&nbsp;1.5g</span>
    all_text = soup.get_text()
    
    # Define patterns for each nutrient
    patterns = {
        "total_fat": r"Total Fat[^0-9]*?(\d+(?:\.\d+)?)g",
        "saturated_fat": r"Saturated Fat[^0-9]*?(\d+(?:\.\d+)?)g",
        "trans_fat": r"Trans.*?Fat[^0-9]*?(\d+(?:\.\d+)?)g",
        "cholesterol": r"Cholesterol[^0-9]*?(\d+(?:\.\d+)?)mg",
        "sodium": r"Sodium[^0-9]*?(\d+(?:\.\d+)?)mg",
        "total_carbs": r"Total Carbohydrate[^0-9]*?(\d+(?:\.\d+)?)g",
        "dietary_fiber": r"Dietary Fiber[^0-9]*?(\d+(?:\.\d+)?)g", 
        "total_sugars": r"Total Sugars[^0-9]*?(\d+(?:\.\d+)?)g",
        "added_sugars": r"Added Sugars[^0-9]*?(\d+(?:\.\d+)?)g",
        "protein": r"Protein[^0-9]*?(\d+(?:\.\d+)?)g",
        "calcium": r"Calcium[^0-9]*?(\d+(?:\.\d+)?)mg",
        "iron": r"Iron[^0-9]*?(\d+(?:\.\d+)?)mg",
        "potassium": r"Potas\.[^0-9]*?(\d+(?:\.\d+)?)mg",
    }

    for nutrient_key, pattern in patterns.items():
        match = re.search(pattern, all_text, re.IGNORECASE)
        if match:
            try:
                nutrition[nutrient_key] = int(float(match.group(1)))
            except ValueError:
                nutrition[nutrient_key] = 0

    return nutrition


# -------------------------------------------------------------
# SCRAPING LOGIC
# -------------------------------------------------------------

def _gather_items_from_page(page) -> List[Tuple[str, str]]:
    """Extract (itemID, name) pairs from the current DOM."""
    return page.evaluate(
        r"""
        () => Array.from(document.querySelectorAll('a.cbo_nn_itemHover')).map(el => {
            const rawAttr = el.dataset.itemid || el.getAttribute('data-itemid') || '';
            const onclick = el.getAttribute('onclick') || '';
            const idMatch = rawAttr || (onclick.match(/\d+/) || [])[0];
            return [idMatch, el.textContent.trim()];
        });
        """
    )


def collect_items_and_nutrition() -> List[Tuple[str, str, Dict[str, int]]]:
    """Return a list of (item_name, restaurant_name, nutrition_dict) tuples scraped from the web UI."""
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        # Use desktop viewport to avoid mobile-specific modals
        context = browser.new_context(viewport={"width": 1280, "height": 720})
        page = context.new_page()

        page.goto(BASE_URL, wait_until="networkidle")

        # Close any modal dialogs that might be blocking interactions
        try:
            # Close mobile disclaimer modal if present
            modal_close = page.locator("#cbo_nn_mobileDisclaimer button.close")
            if modal_close.is_visible():
                modal_close.click()
                page.wait_for_load_state("networkidle")
        except Exception:
            pass
            
        try:
            # Close general popup if present
            page.locator("button.close").first.click(timeout=3000)
        except Exception:
            pass

        # Enter the requested dining unit
        unit_locator = page.locator(f"a[title='{UNIT_NAME}'][data-type='UN']").first

        if unit_locator.count() == 0:
            raise RuntimeError(
                f"Could not find unit '{UNIT_NAME}'. Check spelling on the NetNutrition landing page.")

        clicked = False

        # First attempt: scroll + click with force
        try:
            unit_locator.scroll_into_view_if_needed()
            unit_locator.click(force=True, timeout=5000)
            clicked = True
        except Exception:
            pass

        # Second attempt: Use in-page JS helper NetNutrition.UI.handleNavBarSelection
        if not clicked:
            try:
                page.evaluate(
                    f"""() => {{
                        const el = document.querySelector(\"a[title='{UNIT_NAME}'][data-type='UN']\");
                        if (el && window.NetNutrition?.UI?.handleNavBarSelection) {{
                            window.NetNutrition.UI.handleNavBarSelection(el);
                        }} else if (el) {{
                            el.click();
                        }}
                    }}"""
                )
                clicked = True
            except Exception:
                pass

        if not clicked:
            raise RuntimeError(f"Failed to activate unit '{UNIT_NAME}'. UI may have changed.")
        
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        # Collect all food items and their nutrition data by clicking each one
        all_items_nutrition: List[Tuple[str, str, Dict[str, int]]] = []
        processed_names = set()

        # Check if this restaurant has meal period links (like Breakfast, All Day, etc.)
        # These appear as links in the main content area after selecting a restaurant
        
        # Try looking for meal period links with different strategies
        orange_links = page.locator("a[style*='color'][href*='menuid'], a.text-warning[href*='menuid'], a[href*='menuid']").all()
        if orange_links:
            meal_period_links = orange_links
        else:
            # Try looking for links with specific text patterns (common in dropdown menus)
            text_links = page.locator("a:has-text('Breakfast'), a:has-text('All Day'), a:has-text('Specialty'), a:has-text('Lunch'), a:has-text('Dinner')").all()
            if text_links:
                meal_period_links = text_links

        if meal_period_links:
            print(f"Found {len(meal_period_links)} meal periods for {UNIT_NAME}")
            
            # Process each meal period (Breakfast, All Day, Specialty Drinks, etc.)
            for meal_period in meal_period_links:
                try:
                    meal_period_name = meal_period.text_content().strip()
                    print(f"Processing meal period: {meal_period_name}")
                    
                    # Use JavaScript to handle meal period selection since these are dropdown items
                    meal_id = meal_period.get_attribute("data-mealoid")
                    unit_id = meal_period.get_attribute("data-unitoid") 
                    
                    page.evaluate(f"""
                        () => {{
                            const element = document.querySelector('[data-mealoid="{meal_id}"][data-unitoid="{unit_id}"]');
                            if (element && window.NetNutrition?.UI?.handleNavBarSelection) {{
                                window.NetNutrition.UI.handleNavBarSelection(element);
                            }}
                        }}
                    """)
                    
                    page.wait_for_load_state("networkidle")
                    time.sleep(1)
                    
                    # Now process any meal tabs within this period (if they exist)
                    meal_tabs = page.locator("a.cbo_nn_menuLink").all()
                    tabs_to_process = [None] + meal_tabs if meal_tabs else [None]
                    
                    for meal_tab in tabs_to_process:
                        if meal_tab:
                            try:
                                meal_tab.click()
                                page.wait_for_load_state("networkidle")
                                time.sleep(0.8)
                            except Exception as e:
                                print(f"[!] Failed to process meal tab: {e}")
                                continue

                        # Expand locations so all items are visible
                        page.evaluate(
                            """() => {
                                document
                                    .querySelectorAll('#itemPanel table tbody tr td div')
                                    .forEach(btn => btn.click());
                            }"""
                        )
                        time.sleep(0.5)

                        # Get all food items on this tab
                        food_items = page.locator("a.cbo_nn_itemHover").all()
                        
                        for food_item in food_items:
                            try:
                                food_name = food_item.text_content().strip()
                                
                                # Skip if we've already processed this item
                                if food_name in processed_names:
                                    continue
                                
                                processed_names.add(food_name)
                                
                                # Extract nutrition data
                                nutrition_data = extract_nutrition_from_item(page, food_item, food_name)
                                all_items_nutrition.append((food_name, UNIT_NAME, nutrition_data))
                                
                            except Exception as e:
                                print(f"[!] Failed to process food item: {e}")
                                
                except Exception as e:
                    print(f"[!] Failed to process meal period {meal_period_name}: {e}")
        else:
            print(f"No meal periods found for {UNIT_NAME}, using standard meal tab approach")
            
            # Original approach for restaurants without meal periods
            meal_tabs = page.locator("a.cbo_nn_menuLink").all()
            tabs_to_process = [None] + meal_tabs

            for meal_tab in tabs_to_process:
                if meal_tab:
                    try:
                        meal_tab.click()
                        page.wait_for_load_state("networkidle")
                        time.sleep(0.8)
                    except Exception as e:
                        print(f"[!] Failed to process meal tab: {e}")
                        continue

                # Expand locations so all items are visible
                page.evaluate(
                    """() => {
                        document
                            .querySelectorAll('#itemPanel table tbody tr td div')
                            .forEach(btn => btn.click());
                    }"""
                )
                time.sleep(0.5)

                # Get all food items on this tab
                food_items = page.locator("a.cbo_nn_itemHover").all()
                
                for food_item in food_items:
                    try:
                        food_name = food_item.text_content().strip()
                        
                        # Skip if we've already processed this item
                        if food_name in processed_names:
                            continue
                        
                        processed_names.add(food_name)
                        
                        # Extract nutrition data
                        nutrition_data = extract_nutrition_from_item(page, food_item, food_name)
                        all_items_nutrition.append((food_name, UNIT_NAME, nutrition_data))
                        
                    except Exception as e:
                        print(f"[!] Failed to process food item: {e}")

        browser.close()
        return all_items_nutrition


def extract_nutrition_from_item(page, food_item, food_name):
    """Helper function to extract nutrition data from a food item."""
    # Dismiss any blocking modals before clicking
    try:
        modal = page.locator("#cbo_nn_mobileDisclaimer")
        if modal.is_visible():
            page.locator("#cbo_nn_mobileDisclaimer button.close").click()
            page.wait_for_load_state("networkidle")
    except Exception:
        pass
    
    # Click the food item to open nutrition popup
    food_item.scroll_into_view_if_needed()
    food_item.click(force=True)
    
    # Wait for nutrition popup to appear
    try:
        page.wait_for_selector("#nutritionLabel", timeout=5000)
        
        # Extract nutrition data from the popup
        nutrition_html = page.locator("#nutritionLabel").inner_html()
        nutrition_data = parse_nutrition_html(nutrition_html)
        
        if nutrition_data["calories"] > 0:
            print(f"✓ Extracted {food_name} from {UNIT_NAME} - {nutrition_data['calories']} cal")
        else:
            print(f"⚠ Extracted {food_name} from {UNIT_NAME} - no nutrition data")
        
        # Close the nutrition popup
        close_button = page.locator("#btn_nn_nutrition_close")
        if close_button.is_visible():
            close_button.click()
            page.wait_for_load_state("networkidle")
        
        return nutrition_data
        
    except Exception as e:
        print(f"[!] Failed to extract nutrition for {food_name}: {e}")
        # Try to close any open popup
        try:
            page.locator("#btn_nn_nutrition_close").click(timeout=1000)
        except:
            pass
        
        # Return empty nutrition data
        return {key: 0 for key in LABEL_MAP.values()}


def store_nutrition_data(items_nutrition: List[Tuple[str, str, Dict[str, int]]]):
    """Store nutrition data directly in the database."""
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()

    insert_sql = (
        "INSERT OR REPLACE INTO items ("
        + ", ".join(DB_COLUMNS)
        + ") VALUES ("
        + ", ".join(["?" for _ in DB_COLUMNS])
        + ")"
    )

    success_count = 0
    for name, restaurant, nutrition in items_nutrition:
        try:
            row = [
                name,
                restaurant,
                nutrition["calories"],
                nutrition["total_fat"],
                nutrition["saturated_fat"],
                nutrition["trans_fat"],
                nutrition["cholesterol"],
                nutrition["sodium"],
                nutrition["total_carbs"],
                nutrition["dietary_fiber"],
                nutrition["total_sugars"],
                nutrition["added_sugars"],
                nutrition["protein"],
                nutrition["calcium"],
                nutrition["iron"],
                nutrition["potassium"],
            ]
            cur.execute(insert_sql, row)
            
            if nutrition["calories"] > 0:
                success_count += 1
                
        except Exception as e:
            print(f"[!] Failed to store {name}: {e}")
    
    conn.commit()
    conn.close()
    print(f"\nSummary: {success_count}/{len(items_nutrition)} items had nutrition data")


# -------------------------------------------------------------
# ENTRY POINT
# -------------------------------------------------------------

def main():
    ensure_dependencies()
    setup_database()

    print("Collecting items and nutrition data …")
    items_nutrition = collect_items_and_nutrition()
    print(f"Found {len(items_nutrition)} unique items. Storing in database …")

    store_nutrition_data(items_nutrition)
    print("Done! Data available in", DB_PATH)


if __name__ == "__main__":
    main() 