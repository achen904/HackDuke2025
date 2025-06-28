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
    "meal_period",
    "section",
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
    
    # Check current table structure
    cur.execute("PRAGMA table_info(items)")
    columns = [row[1] for row in cur.fetchall()]
    
    # Check if we need to reorder columns (section should be after meal_period)
    if "section" in columns:
        # Get the position of section column
        section_position = None
        meal_period_position = None
        for i, (_, name, _, _, _, _) in enumerate(cur.execute("PRAGMA table_info(items)").fetchall()):
            if name == "section":
                section_position = i
            elif name == "meal_period":
                meal_period_position = i
        
        # If section is not right after meal_period, we need to reorder
        if section_position is not None and meal_period_position is not None and section_position != meal_period_position + 1:
            print("Reordering columns to put section after meal_period...")
            
            # Create new table with correct column order
            cur.execute("""
                CREATE TABLE items_new (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    restaurant TEXT,
                    meal_period TEXT DEFAULT 'All Day',
                    section TEXT DEFAULT 'General',
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
                    UNIQUE(name, restaurant, meal_period, section)
                )
            """)
            
            # Copy data from old table to new table
            cur.execute("""
                INSERT INTO items_new (name, restaurant, meal_period, section, calories, total_fat, 
                                     saturated_fat, trans_fat, cholesterol, sodium, total_carbs, 
                                     dietary_fiber, total_sugars, added_sugars, protein, calcium, 
                                     iron, potassium)
                SELECT name, restaurant, meal_period, section, calories, total_fat, 
                       saturated_fat, trans_fat, cholesterol, sodium, total_carbs, 
                       dietary_fiber, total_sugars, added_sugars, protein, calcium, 
                       iron, potassium
                FROM items
            """)
            
            # Drop old table and rename new table
            cur.execute("DROP TABLE items")
            cur.execute("ALTER TABLE items_new RENAME TO items")
            conn.commit()
            print("Column reordering complete!")
    
    # Handle cases where columns don't exist yet
    if "meal_period" not in columns:
        print("Adding meal_period column to existing database...")
        cur.execute("ALTER TABLE items ADD COLUMN meal_period TEXT DEFAULT 'All Day'")
        conn.commit()
    
    if "section" not in columns:
        print("Adding section column to existing database...")
        cur.execute("ALTER TABLE items ADD COLUMN section TEXT DEFAULT 'General'")
        conn.commit()
    
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT,
            restaurant TEXT,
            meal_period TEXT DEFAULT 'All Day',
            section TEXT DEFAULT 'General',
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
            UNIQUE(name, restaurant, meal_period, section)
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

def should_update_section(current_section: str, new_section: str) -> bool:
    """Determine if we should update to a new section based on priority."""
    # Define section priority (higher number = higher priority = more specific/primary)
    section_priorities = {
        # Primary categories (specific food types)
        'entrees': 100,
        'mains': 100,
        'main course': 100,
        'burgers': 90,
        'pizza': 90,
        'sandwiches': 85,
        'salads': 85,
        'desserts': 80,
        'sides': 75,
        
        # Secondary categories (modifiers/additions)
        'toppings': 50,
        'add ons': 40,
        'add-ons': 40,
        'extras': 40,
        'condiments': 35,
        'dressings': 35,
        'sauces': 35,
        
        # Generic/fallback categories
        'general': 10,
        'other': 10,
        'build your own': 20,
    }
    
    def get_section_priority(section: str) -> int:
        """Get priority score for a section, checking for partial matches."""
        section_lower = section.lower()
        
        # Exact match first
        if section_lower in section_priorities:
            return section_priorities[section_lower]
        
        # Partial matches
        for key, priority in section_priorities.items():
            if key in section_lower:
                return priority
        
        # Default priority for unknown sections
        # Longer, more descriptive names get higher priority
        if len(section) > 20:
            return 60  # Descriptive sections like "Build Your Own Burger (Choose Your Ingredients)"
        elif len(section) > 10:
            return 30  # Medium descriptive
        else:
            return 15  # Short/generic
    
    current_priority = get_section_priority(current_section)
    new_priority = get_section_priority(new_section)
    
    return new_priority > current_priority


def _gather_items_from_page(page) -> List[Tuple[str, str]]:
    """Extract (itemID, name) pairs from the current DOM."""
    # First try the original selector
    items = page.evaluate(
        r"""
        () => Array.from(document.querySelectorAll('a.cbo_nn_itemHover')).map(el => {
            const rawAttr = el.dataset.itemid || el.getAttribute('data-itemid') || '';
            const onclick = el.getAttribute('onclick') || '';
            const idMatch = rawAttr || (onclick.match(/\d+/) || [])[0];
            return [idMatch, el.textContent.trim()];
        });
        """
    )
    
    # If that didn't work, try alternative selectors and log what we find
    if not items:
        # Debug: Log what elements are actually present
        debug_info = page.evaluate(
            r"""
            () => {
                const results = {
                    itemHover: document.querySelectorAll('a.cbo_nn_itemHover').length,
                    allLinks: document.querySelectorAll('a').length,
                    itemPanel: document.querySelector('#itemPanel') ? 'found' : 'missing',
                    tableRows: document.querySelectorAll('#itemPanel table tbody tr').length,
                    linksInPanel: document.querySelectorAll('#itemPanel a').length,
                    sample_links: Array.from(document.querySelectorAll('#itemPanel a')).slice(0, 5).map(el => ({
                        text: el.textContent.trim(),
                        class: el.className,
                        onclick: el.getAttribute('onclick') || 'none',
                        href: el.href || 'none'
                    }))
                };
                return results;
            }
            """
        )
        print(f"[DEBUG] Page analysis: {debug_info}")
        
        # Try alternative selectors
        alternatives = [
            'a[onclick*="showLabel"]',
            'a[data-itemid]',
            '#itemPanel a[onclick]',
            '#itemPanel table a',
            'a.menuItem',
            'a.food-item'
        ]
        
        for selector in alternatives:
            items = page.evaluate(
                f"""
                () => Array.from(document.querySelectorAll('{selector}')).map(el => {{
                    const rawAttr = el.dataset.itemid || el.getAttribute('data-itemid') || '';
                    const onclick = el.getAttribute('onclick') || '';
                    const idMatch = rawAttr || (onclick.match(/\\d+/) || [])[0];
                    return [idMatch, el.textContent.trim()];
                }});
                """
            )
            if items:
                print(f"[DEBUG] Found {len(items)} items with selector: {selector}")
                break
    
    return items


def collect_items_and_nutrition(unit_name: str) -> List[Tuple[str, str, str, str, Dict[str, int]]]:
    """Return a list of (item_name, restaurant_name, meal_period, section, nutrition_dict) tuples scraped from the web UI."""
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
        unit_locator = page.locator(f"a[title='{unit_name}'][data-type='UN']").first

        if unit_locator.count() == 0:
            raise RuntimeError(
                f"Could not find unit '{unit_name}'. Check spelling on the NetNutrition landing page.")

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
                        const el = document.querySelector(\"a[title='{unit_name}'][data-type='UN']\");
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
            raise RuntimeError(f"Failed to activate unit '{unit_name}'. UI may have changed.")
        
        page.wait_for_load_state("networkidle")
        time.sleep(1)

        # Collect all food items and their nutrition data
        all_items_nutrition: List[Tuple[str, str, str, str, Dict[str, int]]] = []
        processed_names = {}  # Changed to dict to store section info for priority comparison

        # Check if this restaurant has meal period links (like Breakfast, Lunch, Dinner, etc.)
        print(f"Checking for meal periods in {unit_name}...")
        
        # Look for meal period links with different strategies
        meal_period_links = []
        
        # Strategy 1: Look for links with meal period text patterns (expanded to include combo meals)
        text_links = page.locator("a:has-text('Breakfast'), a:has-text('All Day'), a:has-text('Specialty'), a:has-text('Lunch'), a:has-text('Dinner'), a:has-text('Combo'), a:has-text('Brunch'), a:has-text('Late Night')").all()
        
        # Strategy 2: Also look for any links with data-mealoid attribute (broader search)
        mealoid_links = page.locator("a[data-mealoid]").all()
        
        # Combine both strategies
        all_potential_links = text_links + mealoid_links
        
        # Filter to only include links that have proper meal period attributes
        seen_meal_ids = set()
        for link in all_potential_links:
            try:
                text = link.text_content().strip()
                meal_id = link.get_attribute("data-mealoid")
                
                # Skip if we've already seen this meal ID or if it's invalid
                if not meal_id or meal_id in seen_meal_ids or meal_id == "-1":
                    continue
                
                # Check if it looks like a meal period (broader criteria)
                meal_keywords = ['Breakfast', 'All Day', 'Specialty', 'Lunch', 'Dinner', 'Combo', 'Brunch', 'Late Night', 'Menu']
                has_period_text = any(keyword.lower() in text.lower() for keyword in meal_keywords)
                
                # Also include if it has a valid mealoid and reasonable text length
                if has_period_text or (meal_id and len(text) > 2 and len(text) < 50):
                    meal_period_links.append(link)
                    seen_meal_ids.add(meal_id)
                    print(f"Found meal period: '{text}' (mealoid: {meal_id})")
                    
            except Exception:
                continue
        
        print(f"Found {len(meal_period_links)} meal periods for {unit_name}")
        
        # Try the meal period approach if we found any, but with fallback logic
        if meal_period_links:
            print(f"Using meal period approach for {unit_name}")
            
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
                            console.log('Clicking meal period: {meal_period_name}');
                            // Try multiple approaches to activate the meal period
                            
                            // Approach 1: Direct click
                            const link = document.querySelector('a[data-mealoid="{meal_id}"]');
                            if (link) {{
                                link.click();
                                return;
                            }}
                            
                            // Approach 2: Use NetNutrition API if available
                            if (window.NetNutrition && window.NetNutrition.UI) {{
                                window.NetNutrition.UI.showMealPeriod('{meal_id}', '{unit_id}');
                            }}
                        }}
                    """)
                    
                    page.wait_for_load_state("networkidle")
                    time.sleep(2)
                    
                    # Expand locations so all items are visible
                    page.evaluate(
                        """() => {
                            document
                                .querySelectorAll('#itemPanel table tbody tr td div')
                                .forEach(btn => btn.click());
                        }"""
                    )
                    time.sleep(1)
                    
                    # Process items in this meal period with section detection
                    sections = page.locator("#itemPanel table tbody tr").all()
                    current_section = "General"
                    
                    # DEBUG: Let's see the actual HTML structure
                    print(f"  [DEBUG] Found {len(sections)} rows in itemPanel")
                    if len(sections) > 0:
                        # Dump the first few rows to see the structure
                        for i, section_row in enumerate(sections[:5]):
                            try:
                                row_html = section_row.inner_html()
                                row_text = section_row.text_content().strip()
                                print(f"  [DEBUG] Row {i}: text='{row_text[:100]}...'")
                                print(f"  [DEBUG] Row {i}: HTML={row_html[:200]}...")
                                
                                # Check what links are actually in this row
                                all_links = section_row.locator("a").all()
                                print(f"  [DEBUG] Row {i}: found {len(all_links)} total links")
                                for j, link in enumerate(all_links):
                                    link_text = link.text_content().strip()
                                    link_class = link.get_attribute("class") or ""
                                    link_onclick = link.get_attribute("onclick") or ""
                                    print(f"    Link {j}: text='{link_text}' class='{link_class}' onclick='{link_onclick[:50]}...'")
                                    
                            except Exception as e:
                                print(f"  [DEBUG] Error examining row {i}: {e}")
                    
                    # Also check if there are items outside the table structure
                    print(f"  [DEBUG] Checking for items outside table structure...")
                    page_debug = page.evaluate(
                        """
                        () => {
                            return {
                                total_links: document.querySelectorAll('a').length,
                                itemPanel_links: document.querySelectorAll('#itemPanel a').length,
                                itemHover_links: document.querySelectorAll('a.cbo_nn_itemHover').length,
                                onclick_links: document.querySelectorAll('a[onclick]').length,
                                showLabel_links: document.querySelectorAll('a[onclick*="showLabel"]').length,
                                sample_onclick_links: Array.from(document.querySelectorAll('#itemPanel a[onclick]')).slice(0,3).map(el => ({
                                    text: el.textContent.trim(),
                                    onclick: el.getAttribute('onclick')
                                }))
                            };
                        }
                        """
                    )
                    print(f"  [DEBUG] Page analysis: {page_debug}")
                    
                    for section_row in sections:
                        try:
                            section_text = section_row.text_content().strip()
                            food_links_in_row = section_row.locator("a.cbo_nn_itemHover").all()
                            
                            # FIRST: Filter out UI text and comparison elements, but ONLY if there are no food links
                            # Don't skip rows that contain food items even if they have UI text
                            if section_text and not food_links_in_row:
                                text_lower = section_text.lower()
                                skip_patterns = [
                                    'click here', 'view details', 'more info', 'see all',
                                    'add to cart', 'order now', 'select item'
                                ]
                                
                                # Only skip if it's purely UI text with no food items
                                if any(skip_pattern in text_lower for skip_pattern in skip_patterns):
                                    continue
                            
                            # Enhanced section detection - check multiple patterns
                            is_section_header = False
                            potential_section = None
                            
                            # Pattern 1: Row with no food links (original logic)
                            if not food_links_in_row and section_text and len(section_text) > 5:
                                potential_section = section_text.replace("►", "").replace("▶", "").strip()
                                is_section_header = True
                            
                            # Pattern 2: Look for rows that contain section-like text patterns
                            elif section_text and len(section_text) > 5:
                                # Check if this looks like a section header based on content
                                section_indicators = ['crepe', 'salad', 'sandwich', 'coffee', 'tea', 'smoothie', 'gelato', 
                                                    'panini', 'burrito', 'pastry', 'quiche', 'latte', 'frappe']
                                text_lower = section_text.lower()
                                
                                # If text contains section indicators and is relatively short (likely a header)
                                if any(indicator in text_lower for indicator in section_indicators) and len(section_text) < 100:
                                    # Additional validation: should look like a proper menu section
                                    # Check for reasonable section name patterns
                                    words = section_text.split()
                                    
                                    # Skip if it has too many words or looks like a description
                                    if len(words) > 8:
                                        continue
                                    
                                    # Skip if it contains obvious non-section words
                                    non_section_words = ['item', 'info', 'compare', 'nutrition', 'click', 'view', 'details']
                                    if any(word.lower() in text_lower for word in non_section_words):
                                        continue
                                    
                                    # Check if this row has mostly non-food content (section header with some elements)
                                    if len(food_links_in_row) <= 1:  # Allow up to 1 food link in section headers
                                        potential_section = section_text.replace("►", "").replace("▶", "").strip()
                                        is_section_header = True
                            
                            # Pattern 3: Check for specific formatting that indicates section headers
                            elif section_text:
                                # Look for text that's formatted like a section header (caps, short, etc.)
                                words = section_text.split()
                                if (len(words) <= 6 and len(section_text) < 80 and 
                                    not food_links_in_row and section_text.replace(" ", "").isalnum()):
                                    potential_section = section_text.replace("►", "").replace("▶", "").strip()
                                    is_section_header = True
                            
                            # Update current section if we found a valid section header
                            if is_section_header and potential_section and potential_section != current_section:
                                current_section = potential_section
                                print(f"  Found section: {current_section}")
                            
                            # Debug: Log what we found in this row
                            if section_text and len(food_links_in_row) > 0:
                                print(f"  Row contains: '{section_text[:50]}...' with {len(food_links_in_row)} food links")
                            elif section_text and len(section_text) > 5:
                                # This might be a section header
                                print(f"  Potential section header: '{section_text[:50]}...'")
                            
                            # Debug: If no food links found, try alternative approaches
                            if not food_links_in_row and section_text:
                                # Try different selectors for food items in this row
                                alt_selectors = [
                                    "a[onclick*='showLabel']",
                                    "a[data-itemid]", 
                                    "a[onclick]",
                                    "a"
                                ]
                                
                                for selector in alt_selectors:
                                    alt_links = section_row.locator(selector).all()
                                    if alt_links:
                                        print(f"  Found {len(alt_links)} links with selector '{selector}' in row: {section_text[:30]}...")
                                        # Check if these look like food items
                                        for link in alt_links:
                                            link_text = link.text_content().strip()
                                            onclick = link.get_attribute("onclick") or ""
                                            if link_text and len(link_text) > 2 and len(link_text) < 100:
                                                if "showLabel" in onclick or "itemid" in onclick.lower():
                                                    print(f"    Potential food item: '{link_text}' (onclick: {onclick[:30]}...)")
                                                    # Use this as a food item
                                                    food_links_in_row.append(link)
                                        break
                            
                            # Process food items in this row
                            for food_item in food_links_in_row:
                                try:
                                    food_name = food_item.text_content().strip()
                                    onclick = food_item.get_attribute("onclick") or ""
                                    
                                    # Validate this is actually a food item
                                    if not food_name or len(food_name) < 2:
                                        continue
                                        
                                    # Skip obvious UI elements - be more specific to avoid false positives
                                    skip_text = ['click here', 'view details', 'more info', 'see all', 'add to cart']
                                    if any(skip in food_name.lower() for skip in skip_text):
                                        continue
                                    
                                    print(f"  Processing food item: '{food_name}' in section '{current_section}'")
                                    
                                    # Extract item ID from onclick attribute for true uniqueness
                                    onclick = food_item.get_attribute("onclick") or ""
                                    item_id = None
                                    if "getItemNutritionLabel" in onclick:
                                        import re
                                        match = re.search(r'getItemNutritionLabelOnClick\(event,(\d+)\)', onclick)
                                        if match:
                                            item_id = match.group(1)
                                    
                                    # Create unique key using item ID if available (ignore meal period for true uniqueness)
                                    if item_id:
                                        unique_key = f"{item_id}_{unit_name}"
                                    else:
                                        unique_key = f"{food_name}_{unit_name}_{meal_period_name}"
                                    
                                    # Check if we've seen this item before
                                    if unique_key in processed_names:
                                        # Check if current section has higher priority than stored section
                                        stored_item = processed_names[unique_key]
                                        if should_update_section(stored_item['section'], current_section):
                                            print(f"  Updating section for {food_name}: '{stored_item['section']}' → '{current_section}'")
                                            # Update the stored item with better section
                                            for i, item in enumerate(all_items_nutrition):
                                                if item[0] == food_name and item[1] == unit_name:
                                                    all_items_nutrition[i] = (food_name, unit_name, meal_period_name, current_section, item[4])
                                                    break
                                            processed_names[unique_key]['section'] = current_section
                                        else:
                                            if item_id:
                                                print(f"  Skipping duplicate: {food_name} (same item ID: {item_id}, keeping section: {stored_item['section']})")
                                            else:
                                                print(f"  Skipping duplicate: {food_name} (same name, keeping section: {stored_item['section']})")
                                        continue
                                    
                                    # Store item info for future section comparisons
                                    processed_names[unique_key] = {
                                        'section': current_section,
                                        'meal_period': meal_period_name,
                                        'name': food_name
                                    }
                                    
                                    # Extract nutrition data
                                    nutrition_data = extract_nutrition_from_item(page, food_item, food_name, unit_name, meal_period_name)
                                    all_items_nutrition.append((food_name, unit_name, meal_period_name, current_section, nutrition_data))
                                    
                                except Exception as e:
                                    print(f"  [!] Failed to process food item: {e}")
                                    
                        except Exception as e:
                            print(f"  [!] Failed to process section row: {e}")
                    
                    meal_items = [item for item in all_items_nutrition if item[2] == meal_period_name]
                    print(f"  Completed {meal_period_name}: found {len(meal_items)} items")
                    
                except Exception as e:
                    print(f"[!] Failed to process meal period {meal_period_name}: {e}")
            
            # For restaurants with many meal periods but same items, default to "All Day"
            if all_items_nutrition:
                # Check if this restaurant should be treated as "All Day" instead of specific meal periods
                if len(meal_period_links) > 6:  # If many meal periods detected (likely same items everywhere)
                    print(f"Restaurant has {len(meal_period_links)} meal periods - likely an 'All Day' restaurant")
                    print("Converting all meal periods to 'All Day' for consistency")
                    
                    # Convert all items to "All Day" meal period
                    all_items_nutrition = [
                        (item_name, restaurant, "All Day", section, nutrition)
                        for item_name, restaurant, meal_period, section, nutrition in all_items_nutrition
                    ]
                
                print(f"Successfully extracted {len(all_items_nutrition)} items using meal period approach")
            else:
                print("Meal period approach found no items, falling back to standard approach")
        
        # Fallback: Use standard approach if no meal periods or meal period approach failed
        if not meal_period_links or not all_items_nutrition:
            print(f"Using standard approach for {unit_name}...")
            
            # Standard approach - works for restaurants without meal periods
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

                # Get all food items and their section headings
                sections = page.locator("#itemPanel table tbody tr").all()
                current_section = "General"
                
                for section_row in sections:
                    try:
                        section_text = section_row.text_content().strip()
                        food_links_in_row = section_row.locator("a.cbo_nn_itemHover").all()
                        
                        # FIRST: Filter out UI text and comparison elements, but ONLY if there are no food links
                        # Don't skip rows that contain food items even if they have UI text
                        if section_text and not food_links_in_row:
                            text_lower = section_text.lower()
                            skip_patterns = [
                                'click here', 'view details', 'more info', 'see all',
                                'add to cart', 'order now', 'select item'
                            ]
                            
                            # Only skip if it's purely UI text with no food items
                            if any(skip_pattern in text_lower for skip_pattern in skip_patterns):
                                continue
                        
                        # Enhanced section detection - check multiple patterns
                        is_section_header = False
                        potential_section = None
                        
                        # Pattern 1: Row with no food links (original logic)
                        if not food_links_in_row and section_text and len(section_text) > 5:
                            potential_section = section_text.replace("►", "").replace("▶", "").strip()
                            is_section_header = True
                        
                        # Pattern 2: Look for rows that contain section-like text patterns
                        elif section_text and len(section_text) > 5:
                            # Check if this looks like a section header based on content
                            section_indicators = ['crepe', 'salad', 'sandwich', 'coffee', 'tea', 'smoothie', 'gelato', 
                                                'panini', 'burrito', 'pastry', 'quiche', 'latte', 'frappe']
                            text_lower = section_text.lower()
                            
                            # If text contains section indicators and is relatively short (likely a header)
                            if any(indicator in text_lower for indicator in section_indicators) and len(section_text) < 100:
                                # Additional validation: should look like a proper menu section
                                # Check for reasonable section name patterns
                                words = section_text.split()
                                
                                # Skip if it has too many words or looks like a description
                                if len(words) > 8:
                                    continue
                                
                                # Skip if it contains obvious non-section words
                                non_section_words = ['item', 'info', 'compare', 'nutrition', 'click', 'view', 'details']
                                if any(word.lower() in text_lower for word in non_section_words):
                                    continue
                                
                                # Check if this row has mostly non-food content (section header with some elements)
                                if len(food_links_in_row) <= 1:  # Allow up to 1 food link in section headers
                                    potential_section = section_text.replace("►", "").replace("▶", "").strip()
                                    is_section_header = True
                        
                        # Pattern 3: Check for specific formatting that indicates section headers
                        elif section_text:
                            # Look for text that's formatted like a section header (caps, short, etc.)
                            words = section_text.split()
                            if (len(words) <= 6 and len(section_text) < 80 and 
                                not food_links_in_row and section_text.replace(" ", "").isalnum()):
                                potential_section = section_text.replace("►", "").replace("▶", "").strip()
                                is_section_header = True
                        
                        # Update current section if we found a valid section header
                        if is_section_header and potential_section and potential_section != current_section:
                            current_section = potential_section
                            print(f"  Found section: {current_section}")
                        
                        # Debug: Log what we found in this row
                        if section_text and len(food_links_in_row) > 0:
                            print(f"  Row contains: '{section_text[:50]}...' with {len(food_links_in_row)} food links")
                        elif section_text and len(section_text) > 5:
                            # This might be a section header
                            print(f"  Potential section header: '{section_text[:50]}...'")
                        
                        # Debug: If no food links found, try alternative approaches
                        if not food_links_in_row and section_text:
                            # Try different selectors for food items in this row
                            alt_selectors = [
                                "a[onclick*='showLabel']",
                                "a[data-itemid]", 
                                "a[onclick]",
                                "a"
                            ]
                            
                            for selector in alt_selectors:
                                alt_links = section_row.locator(selector).all()
                                if alt_links:
                                    print(f"  Found {len(alt_links)} links with selector '{selector}' in row: {section_text[:30]}...")
                                    # Check if these look like food items
                                    for link in alt_links:
                                        link_text = link.text_content().strip()
                                        onclick = link.get_attribute("onclick") or ""
                                        if link_text and len(link_text) > 2 and len(link_text) < 100:
                                            if "showLabel" in onclick or "itemid" in onclick.lower():
                                                print(f"    Potential food item: '{link_text}' (onclick: {onclick[:30]}...)")
                                                # Use this as a food item
                                                food_links_in_row.append(link)
                                    break
                        
                        # Process food items in this row
                        for food_item in food_links_in_row:
                            try:
                                food_name = food_item.text_content().strip()
                                onclick = food_item.get_attribute("onclick") or ""
                                
                                # Validate this is actually a food item
                                if not food_name or len(food_name) < 2:
                                    continue
                                    
                                # Skip obvious UI elements - be more specific to avoid false positives
                                skip_text = ['click here', 'view details', 'more info', 'see all', 'add to cart']
                                if any(skip in food_name.lower() for skip in skip_text):
                                    continue
                                
                                print(f"  Processing food item: '{food_name}' in section '{current_section}'")
                                
                                # Extract item ID from onclick attribute for true uniqueness
                                onclick = food_item.get_attribute("onclick") or ""
                                item_id = None
                                if "getItemNutritionLabel" in onclick:
                                    import re
                                    match = re.search(r'getItemNutritionLabelOnClick\(event,(\d+)\)', onclick)
                                    if match:
                                        item_id = match.group(1)
                                
                                # Create unique key using item ID if available (ignore meal period for true uniqueness)
                                if item_id:
                                    unique_key = f"{item_id}_{unit_name}"
                                else:
                                    unique_key = f"{food_name}_{unit_name}_All Day"
                                
                                # Check if we've seen this item before
                                if unique_key in processed_names:
                                    # Check if current section has higher priority than stored section
                                    stored_item = processed_names[unique_key]
                                    if should_update_section(stored_item['section'], current_section):
                                        print(f"  Updating section for {food_name}: '{stored_item['section']}' → '{current_section}'")
                                        # Update the stored item with better section
                                        for i, item in enumerate(all_items_nutrition):
                                            if item[0] == food_name and item[1] == unit_name:
                                                all_items_nutrition[i] = (food_name, unit_name, "All Day", current_section, item[4])
                                                break
                                        processed_names[unique_key]['section'] = current_section
                                    else:
                                        if item_id:
                                            print(f"  Skipping duplicate: {food_name} (same item ID: {item_id}, keeping section: {stored_item['section']})")
                                        else:
                                            print(f"  Skipping duplicate: {food_name} (same name, keeping section: {stored_item['section']})")
                                    continue
                                
                                # Store item info for future section comparisons
                                processed_names[unique_key] = {
                                    'section': current_section,
                                    'meal_period': "All Day",
                                    'name': food_name
                                }
                                
                                # Extract nutrition data with "All Day" as meal period and current section
                                nutrition_data = extract_nutrition_from_item(page, food_item, food_name, unit_name, "All Day")
                                all_items_nutrition.append((food_name, unit_name, "All Day", current_section, nutrition_data))
                                
                            except Exception as e:
                                print(f"  [!] Failed to process food item: {e}")
                                
                    except Exception as e:
                        print(f"  [!] Failed to process section row: {e}")

        browser.close()
        return all_items_nutrition


def extract_nutrition_from_item(page, food_item, food_name, restaurant_name, meal_period):
    """Helper function to extract nutrition data from a food item."""
    # Dismiss any blocking modals before clicking
    try:
        modal = page.locator("#cbo_nn_mobileDisclaimer")
        if modal.is_visible():
            page.locator("#cbo_nn_mobileDisclaimer button.close").click()
            page.wait_for_load_state("networkidle")
    except Exception:
        pass
    
    # Try multiple approaches to click the food item
    clicked = False
    nutrition_data = {key: 0 for key in LABEL_MAP.values()}
    
    # Approach 1: Try to use JavaScript to click directly using onclick attribute
    try:
        onclick = food_item.get_attribute("onclick")
        if onclick and "getItemNutritionLabel" in onclick:
            # Extract the item ID from onclick and call the function directly
            import re
            match = re.search(r'getItemNutritionLabelOnClick\(event,(\d+)\)', onclick)
            if match:
                item_id = match.group(1)
                # Create a mock event object with target property
                page.evaluate(f"""
                    const mockEvent = {{ target: document.getElementById('showNutrition_{item_id}') }};
                    NetNutrition.UI.getItemNutritionLabelOnClick(mockEvent, {item_id});
                """)
                clicked = True
                print(f"  → Used direct JavaScript call for {food_name}")
    except Exception as e:
        print(f"  → JavaScript approach failed: {e}")
    
    # Approach 2: Try standard click with reduced timeout
    if not clicked:
        try:
            # Try to scroll with reduced timeout first
            food_item.scroll_into_view_if_needed(timeout=3000)
            food_item.click(force=True, timeout=3000)
            clicked = True
            print(f"  → Used standard click for {food_name}")
        except Exception as e:
            print(f"  → Standard click failed: {e}")
    
    # Approach 3: Try clicking without scrolling
    if not clicked:
        try:
            food_item.click(force=True, timeout=2000)
            clicked = True
            print(f"  → Used force click without scroll for {food_name}")
        except Exception as e:
            print(f"  → Force click failed: {e}")
    
    # Approach 4: Try the simpler nutrition label function without event
    if not clicked:
        try:
            onclick = food_item.get_attribute("onclick")
            if onclick and "getItemNutritionLabel" in onclick:
                import re
                match = re.search(r'getItemNutritionLabelOnClick\(event,(\d+)\)', onclick)
                if match:
                    item_id = match.group(1)
                    # Try the simpler function that might not need an event
                    page.evaluate(f"NetNutrition.UI.getItemNutritionLabel({item_id})")
                    clicked = True
                    print(f"  → Used simple nutrition label call for {food_name}")
        except Exception as e:
            print(f"  → Simple nutrition call failed: {e}")
    
    # Approach 5: Try using JavaScript click by element ID
    if not clicked:
        try:
            # Get the element ID and click via JavaScript
            element_id = food_item.get_attribute("id")
            if element_id:
                page.evaluate(f"document.getElementById('{element_id}').click()")
                clicked = True
                print(f"  → Used JavaScript ID click for {food_name}")
            else:
                # Fallback: use querySelector with onclick attribute
                onclick = food_item.get_attribute("onclick") or ""
                if "getItemNutritionLabel" in onclick:
                    import re
                    match = re.search(r'getItemNutritionLabelOnClick\(event,(\d+)\)', onclick)
                    if match:
                        item_id = match.group(1)
                        page.evaluate(f"document.querySelector('[onclick*=\"{item_id}\"]').click()")
                        clicked = True
                        print(f"  → Used JavaScript selector click for {food_name}")
        except Exception as e:
            print(f"  → JavaScript element click failed: {e}")
    
    # If we successfully clicked, try to extract nutrition data
    if clicked:
        try:
            # Wait for nutrition popup with reduced timeout
            page.wait_for_selector("#nutritionLabel", timeout=3000)
            
            # Extract nutrition data from the popup
            nutrition_html = page.locator("#nutritionLabel").inner_html()
            nutrition_data = parse_nutrition_html(nutrition_html)
            
            if nutrition_data["calories"] > 0:
                print(f"✓ Extracted {food_name} from {restaurant_name} ({meal_period}) - {nutrition_data['calories']} cal")
            else:
                print(f"⚠ Extracted {food_name} from {restaurant_name} ({meal_period}) - no nutrition data")
            
            # Close the nutrition popup
            try:
                close_button = page.locator("#btn_nn_nutrition_close")
                if close_button.is_visible(timeout=1000):
                    close_button.click(timeout=2000)
                    page.wait_for_load_state("networkidle", timeout=3000)
            except Exception:
                # If closing fails, try pressing Escape
                page.keyboard.press("Escape")
            
        except Exception as e:
            print(f"[!] Failed to extract nutrition data for {food_name}: {e}")
            # Try to close any open popup
            try:
                page.locator("#btn_nn_nutrition_close").click(timeout=1000)
            except:
                try:
                    page.keyboard.press("Escape")
                except:
                    pass
    else:
        print(f"⚠ Could not click {food_name} - skipping nutrition extraction")
    
    return nutrition_data


def store_nutrition_data(items_nutrition: List[Tuple[str, str, str, str, Dict[str, int]]]):
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
    for name, restaurant, meal_period, section, nutrition in items_nutrition:
        try:
            row = [
                name,
                restaurant,
                meal_period,
                section,
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


def get_restaurant_name():
    """Prompt user for restaurant name."""
    while True:
        restaurant_name = input("\nEnter restaurant name (or 'stop' to quit): ").strip()
        if restaurant_name.lower() == 'stop':
            return None
        if restaurant_name:
            return restaurant_name
        print("Please enter a valid restaurant name.")


# -------------------------------------------------------------
# ENTRY POINT
# -------------------------------------------------------------

def main():
    ensure_dependencies()
    setup_database()

    print("=== Duke Nutrition Scraper ===")
    print("This tool will continuously prompt for restaurant names to scrape.")
    print("Type 'stop' when you're done.\n")

    while True:
        restaurant_name = get_restaurant_name()
        if restaurant_name is None:
            print("Stopping scraper. Goodbye!")
            break
            
        try:
            print(f"\nCollecting items and nutrition data from '{restaurant_name}'...")
            items_nutrition = collect_items_and_nutrition(restaurant_name)
            print(f"Found {len(items_nutrition)} unique items. Storing in database...")

            store_nutrition_data(items_nutrition)
            print(f"✅ Successfully scraped {restaurant_name}! Data available in {DB_PATH}")
            
        except Exception as e:
            print(f"❌ Error scraping '{restaurant_name}': {e}")
            print("Please check the restaurant name and try again.")


if __name__ == "__main__":
    main() 