import time
import subprocess
import sys
from playwright.sync_api import sync_playwright

def install_missing_packages():
    """Ensures all required packages are installed."""
    packages = ["playwright"]
    for package in packages:
        try:
            __import__(package)
        except ImportError:
            subprocess.check_call([sys.executable, "-m", "pip", "install", package])

def scrape_marketplace_data():
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=False)
        page = browser.new_page()
        
        # Go to NetNutrition website
        menu_url = "https://netnutrition.cbord.com/nn-prod/Duke"
        page.goto(menu_url)
        page.wait_for_load_state("domcontentloaded")
        page.wait_for_load_state("networkidle")

        try:
            # Handle the modal if present
            modal = page.locator("#cbo_nn_mobileDisclaimer")
            if modal.is_visible():
                close_button = modal.locator("button.close")
                if close_button.is_visible():
                    close_button.click()
                    page.wait_for_timeout(1000)

            # Click into Marketplace
            marketplace_link = page.locator("a.text-white:has-text('Marketplace')").first
            marketplace_link.wait_for(state="visible", timeout=15000)
            marketplace_link.scroll_into_view_if_needed()
            marketplace_link.click(timeout=10000)
            page.wait_for_load_state("networkidle")
            time.sleep(3)
        except Exception as e:
            print("Error: Could not find Marketplace link.", e)
            return {}

        # Meal XPaths
        meal_xpaths = {
            "Saturday": {
                "Brunch": "/html/body/div/div[2]/form/div/div[2]/main/div[3]/section/div[2]/div/section/div/div[1]/section/div/div/div[1]/a",
                "Dinner": "/html/body/div/div[2]/form/div/div[2]/main/div[3]/section/div[2]/div/section/div/div[1]/section/div/div/div[2]/a"
            },
            "Sunday": {
                "Brunch": "/html/body/div/div[2]/form/div/div[2]/main/div[3]/section/div[2]/div/section/div/div[2]/section/div/div/div[1]/a",
                "Dinner": "/html/body/div/div[2]/form/div/div[2]/main/div[3]/section/div[2]/div/section/div/div[2]/section/div/div/div[2]/a"
            },
            "Monday": {
                "Breakfast": "/html/body/div/div[2]/form/div/div[2]/main/div[3]/section/div[2]/div/section/div/div[3]/section/div/div/div[1]/a",
                "Lunch": "/html/body/div/div[2]/form/div/div[2]/main/div[3]/section/div[2]/div/section/div/div[3]/section/div/div/div[2]/a",
                "Dinner": "/html/body/div/div[2]/form/div/div[2]/main/div[3]/section/div[2]/div/section/div/div[3]/section/div/div/div[3]/a"
            },
            "Tuesday": {
                "Breakfast": "/html/body/div/div[2]/form/div/div[2]/main/div[3]/section/div[2]/div/section/div/div[4]/section/div/div/div[1]/a",
                "Lunch": "/html/body/div/div[2]/form/div/div[2]/main/div[3]/section/div[2]/div/section/div/div[4]/section/div/div/div[2]/a",
                "Dinner": "/html/body/div/div[2]/form/div/div[2]/main/div[3]/section/div[2]/div/section/div/div[4]/section/div/div/div[3]/a"
            },
            "Wednesday": {
                "Breakfast": "/html/body/div/div[2]/form/div/div[2]/main/div[3]/section/div[2]/div/section/div/div[5]/section/div/div/div[1]/a",
                "Lunch": "/html/body/div/div[2]/form/div/div[2]/main/div[3]/section/div[2]/div/section/div/div[5]/section/div/div/div[2]/a",
                "Dinner": "/html/body/div/div[2]/form/div/div[2]/main/div[3]/section/div[2]/div/section/div/div[5]/section/div/div/div[3]/a"
            },
            "Thursday": {
                "Breakfast": "/html/body/div/div[2]/form/div/div[2]/main/div[3]/section/div[2]/div/section/div/div[6]/section/div/div/div[1]/a",
                "Lunch": "/html/body/div/div[2]/form/div/div[2]/main/div[3]/section/div[2]/div/section/div/div[6]/section/div/div/div[2]/a",
                "Dinner": "/html/body/div/div[2]/form/div/div[2]/main/div[3]/section/div[2]/div/section/div/div[6]/section/div/div/div[3]/a"
            },
            "Friday": {
                "Breakfast": "/html/body/div/div[2]/form/div/div[2]/main/div[3]/section/div[2]/div/section/div/div[7]/section/div/div/div[1]/a",
                "Lunch": "/html/body/div/div[2]/form/div/div[2]/main/div[3]/section/div[2]/div/section/div/div[7]/section/div/div/div[2]/a",
                "Dinner": "/html/body/div/div[2]/form/div/div[2]/main/div[3]/section/div[2]/div/section/div/div[7]/section/div/div/div[3]/a"
            }
        }

        marketplace_data = {}

        for day, meals in meal_xpaths.items():
            marketplace_data[day] = {}
            for meal_name, xpath in meals.items():
                try:
                    print(f"\nProcessing {day} - {meal_name}...")

                    # Click the meal
                    meal_button = page.locator(f"xpath={xpath}")
                    if not meal_button.is_visible():
                        print(f"Meal button for {day} {meal_name} not visible.")
                        continue

                    meal_button.click()
                    page.wait_for_load_state("networkidle")
                    time.sleep(3)

                    # Extract all food items in the meal
                    food_items = page.locator(".cbo_nn_itemHover").all_text_contents()
                    marketplace_data[day][meal_name] = food_items

                    print(f"  -> Found {len(food_items)} items for {meal_name} on {day}")

                    # **Click "Back" button instead of using `go_back()`**
                    back_button = page.locator("a.breadcrumb-item.text-primary:has-text('Back')")
                    if back_button.is_visible():
                        back_button.click()
                        page.wait_for_load_state("networkidle")
                        time.sleep(3)
                    else:
                        print(f"Warning: 'Back' button not found for {day} {meal_name}.")
                        break  # Stop processing if navigation fails

                except Exception as e:
                    print(f"Error processing {day} {meal_name}: {e}")
                    continue

        browser.close()

        # Print structured results
        for day, meals in marketplace_data.items():
            print(f"\n{day}:")
            for meal, foods in meals.items():
                print(f"  {meal}:")
                if foods:
                    for food in foods:
                        print(f"    - {food}")
                else:
                    print("    No items found")

        return marketplace_data

if __name__ == "__main__":
    install_missing_packages()
    marketplace_data = scrape_marketplace_data()
    if not marketplace_data:
        print("No data scraped for Marketplace.")
