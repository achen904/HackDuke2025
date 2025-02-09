import time
import subprocess
import sys
import sqlite3
from playwright.sync_api import sync_playwright
import os

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
    
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS items (
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

    conn.commit()
    conn.close()

def save_to_database(meal, location, food_name, nutrition_info):

    print(nutrition_info)
    """Save extracted data into SQLite database."""
    conn = sqlite3.connect("duke_nutrition.db")
    cursor = conn.cursor()

   
    # Insert food item
    cursor.execute('''
            INSERT INTO items (name, calories, total_fat, saturated_fat, trans_fat, cholesterol, sodium, total_carbs, dietary_fiber, total_sugars, added_sugars, protein, calcium, iron, potassium) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        ''', (nutrition_info[0], nutrition_info[1], nutrition_info[2], nutrition_info[3], nutrition_info[4], nutrition_info[5], nutrition_info[6], nutrition_info[7], nutrition_info[8], nutrition_info[9], nutrition_info[12], nutrition_info[10], nutrition_info[11], 0, 0))

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

            page.evaluate("""
                () => {
                    let buttons = document.querySelectorAll("#itemPanel > section > div.table-responsive.pt-3 > table > tbody > tr > td > div");
                    buttons.forEach(button => {
                        if (button) {
                            button.click();
                        }
                    });
                }
            """)

            visited_foods = set()

            for location_xpath in location_xpaths:
                try:
                    location_element = page.locator(f"xpath={location_xpath}")
                    #location_element.click(force=True)
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
                            
                            #print(f"    🍽 {food_name} - {nutrition_info}")
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
    """Extracts nutrition information from the popup window and returns it as a tuple."""
    try:
        page.wait_for_selector("text=Nutrition Information", state='visible', timeout=5000)

        # Extract individual nutrition facts
        nutrition_data = page.evaluate("""
            () => {
                let rows1 = document.querySelectorAll("#nutritionLabel > div > div > table > tbody > tr");
                let data = [];
                rows1.forEach(row => {
                    let label = row.querySelector("td.cbo_nn_LabelHeader");
                    if (label) {
                        let text = label.textContent.trim();
                        if (text) {
                            data.push(text);
                        }
                    }
                });
                                       
                let rows = document.querySelectorAll("#nutritionLabel > div > div > table > tbody > tr");
                rows.forEach(row => {
                    let label = row.querySelector("td > div.inline-div-right.bold-text.font-22");
                    if (label) {
                        let text = label.textContent.trim();
                        if (text) {
                            data.push(parseInt(text));
                        }
                    }
                });
                                       
                let rows2 = document.querySelectorAll("#nutritionLabel > div > div > table > tbody > tr");
                rows2.forEach(row => {
                    let label = row.querySelector("td > div > div > span:nth-child(2)");
                    if (label) {
                        let text = label.textContent.trim();
                        if (text) {
                            let matches = text.match(/\d+/g);
                            if (matches){
                                data.push(parseInt(matches[0]));
                            }
                            else {
                                data.push(0);
                            }
                        }
                    }
                });
                                       
                let rows3 = document.querySelectorAll("#nutritionLabel > div > div > table > tbody > tr");
                rows3.forEach(row => {
                    let label = row.querySelector("td > div > div.inline-div-left.addedSugarRow > span");
                    if (label) {
                        let text = label.textContent.trim();
                        if (text) {
                            const arr1 = text.split(" ");
                            if (arr1[1] == 'NA'){
                                data.push(0);
                            }
                            else {
                                data.push(parseInt(arr[1]));
                            }
                        }
                    }
                });
                return data;
            }
        """)


        if not nutrition_data:
            return ("No nutrition info available",)

        # Convert list to tuple for consistency
        return tuple(nutrition_data)

    except Exception as e:
        print(f"Error extracting nutrition info: {e}")
        return ("Nutrition info extraction failed",)
    
if __name__ == "__main__":
    os.remove("duke_nutrition.db")
    f = open("duke_nutrition.db", "x")

    install_missing_packages()
    setup_database()
    scrape_marketplace_data()
