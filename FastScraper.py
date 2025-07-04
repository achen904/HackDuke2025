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
    """Parse NetNutrition HTML snippet into a dict keyed by DB column names."""
    soup = BeautifulSoup(html, "html.parser")
    nutrition: Dict[str, int] = {key: 0 for key in LABEL_MAP.values()}

    # First try to find calories
    calories = 0
    calories_patterns = [
        (r'Calories[:\s]*(\d+)', 'text'),  # Basic pattern
        (r'Calories from Fat[:\s]*(\d+)', 'text'),  # Skip this - it's not total calories
        (r'Total Calories[:\s]*(\d+)', 'text'),  # Another variation
        ('div.inline-div-right.bold-text.font-22', 'selector'),  # Original selector
        ('.calories', 'selector'),  # Common class
        ('[data-nutrient="calories"]', 'selector'),  # Data attribute
        ('.nutrition-calories', 'selector'),  # Another common class
    ]
    
    for pattern, pattern_type in calories_patterns:
        if calories > 0:
            break
            
        try:
            if pattern_type == 'text':
                # Skip "Calories from Fat" pattern
                if 'from Fat' in pattern:
                    continue
                # Search in all text
                all_text = soup.get_text()
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    calories = int(match.group(1))
            else:
                # Use CSS selector
                element = soup.select_one(pattern)
                if element:
                    # Try to find number in element text
                    text = element.get_text(strip=True)
                    match = re.search(r'(\d+)', text)
                    if match:
                        calories = int(match.group(1))
        except Exception:
            continue
    
    nutrition['calories'] = calories

    # Enhanced nutrient extraction with better pattern matching
    all_text = soup.get_text()
    
    # Define nutrient-specific patterns to avoid cross-contamination
    nutrient_patterns = {
        'total_fat': [
            r'Total Fat[^0-9]*?(\d+(?:\.\d+)?)\s*g\b',
            r'Fat[^0-9]*?(\d+(?:\.\d+)?)\s*g\b(?!.*Saturated)',  # Fat but not Saturated Fat
        ],
        'saturated_fat': [
            r'Saturated Fat[^0-9]*?(\d+(?:\.\d+)?)\s*g\b',
            r'Sat\.?\s*Fat[^0-9]*?(\d+(?:\.\d+)?)\s*g\b',
        ],
        'trans_fat': [
            r'Trans Fat[^0-9]*?(\d+(?:\.\d+)?)\s*g\b',
            r'Trans[^0-9]*?(\d+(?:\.\d+)?)\s*g\b',
        ],
        'cholesterol': [
            r'Cholesterol[^0-9]*?(\d+(?:\.\d+)?)\s*mg\b',
            r'Chol\.?[^0-9]*?(\d+(?:\.\d+)?)\s*mg\b',
        ],
        'sodium': [
            r'Sodium[^0-9]*?(\d+(?:\.\d+)?)\s*mg\b',
            r'Na[^0-9]*?(\d+(?:\.\d+)?)\s*mg\b',
        ],
        'total_carbs': [
            r'Total Carbohydrate[^0-9]*?(\d+(?:\.\d+)?)\s*g\b',
            r'Total Carbs[^0-9]*?(\d+(?:\.\d+)?)\s*g\b',
            r'Carbohydrate[^0-9]*?(\d+(?:\.\d+)?)\s*g\b(?!.*Dietary)',
        ],
        'dietary_fiber': [
            r'Dietary Fiber[^0-9]*?(\d+(?:\.\d+)?)\s*g\b',
            r'Fiber[^0-9]*?(\d+(?:\.\d+)?)\s*g\b',
        ],
        'total_sugars': [
            r'Total Sugars[^0-9]*?(\d+(?:\.\d+)?)\s*g\b',
            r'(?<!Added\s)(?<!Add\s)Sugars[^0-9]*?(\d+(?:\.\d+)?)\s*g\b(?!\s*Added)',  # Sugars but not Added Sugars
        ],
        'added_sugars': [
            r'Added Sugars[^0-9]*?(\d+(?:\.\d+)?)\s*g\b',
            r'Add\.?\s*Sugars[^0-9]*?(\d+(?:\.\d+)?)\s*g\b',
        ],
        'protein': [
            r'Protein[^0-9]*?(\d+(?:\.\d+)?)\s*g\b',
            r'Prot\.?[^0-9]*?(\d+(?:\.\d+)?)\s*g\b',
        ],
        'calcium': [
            r'Calcium[^0-9]*?(\d+(?:\.\d+)?)\s*mg\b',
            r'Ca[^0-9]*?(\d+(?:\.\d+)?)\s*mg\b',
        ],
        'iron': [
            r'Iron[^0-9]*?(\d+(?:\.\d+)?)\s*mg\b',
            r'Fe[^0-9]*?(\d+(?:\.\d+)?)\s*mg\b',
        ],
        'potassium': [
            r'Potassium[^0-9]*?(\d+(?:\.\d+)?)\s*mg\b',
            r'Potas\.?[^0-9]*?(\d+(?:\.\d+)?)\s*mg\b',
            r'K[^0-9]*?(\d+(?:\.\d+)?)\s*mg\b',
        ],
    }

    # Extract each nutrient using specific patterns
    for nutrient_key, patterns in nutrient_patterns.items():
        value = 0
        
        # Try each pattern for this nutrient
        for pattern in patterns:
            if value > 0:  # Stop if we found a value
                break
                
            try:
                match = re.search(pattern, all_text, re.IGNORECASE)
                if match:
                    value = int(float(match.group(1)))
                    break
            except (ValueError, AttributeError):
                continue
        
        # If no pattern worked, try structured HTML approach
        if value == 0:
            try:
                # Map nutrient key back to label for HTML search
                reverse_label_map = {v: k for k, v in LABEL_MAP.items()}
                label = reverse_label_map.get(nutrient_key, nutrient_key.replace('_', ' ').title())
                
                # Look for label in HTML structure
                label_element = soup.find(string=re.compile(f"^{label}$", re.IGNORECASE))
                if label_element:
                    # Look in siblings and parent's siblings
                    current = label_element.parent
                    for _ in range(3):  # Look up to 3 levels
                        if current:
                            # Check next sibling
                            if current.next_sibling:
                                text = current.next_sibling.get_text(strip=True)
                                match = re.search(r'(\d+(?:\.\d+)?)\s*(?:g|mg)', text)
                                if match:
                                    value = int(float(match.group(1)))
                                    break
                            current = current.parent
            except Exception:
                pass
        
        nutrition[nutrient_key] = value

    return nutrition


# -------------------------------------------------------------
# SCRAPING LOGIC
# -------------------------------------------------------------

def should_update_section(current_section: str, new_section: str) -> bool:
    """Determine if we should update to a new section based on priority."""
    # Enhanced section priority mapping
    section_priorities = {
        # Primary food categories
        'entrees': 100,
        'mains': 100,
        'main course': 100,
        'main dishes': 100,
        'specialties': 95,
        'signature': 95,
        'featured': 95,
        'burgers': 90,
        'pizza': 90,
        'sandwiches': 85,
        'wraps': 85,
        'salads': 85,
        'bowls': 85,
        'pasta': 85,
        'noodles': 85,
        'rice dishes': 85,
        'desserts': 80,
        'sweets': 80,
        'sides': 75,
        'appetizers': 75,
        'starters': 75,
        
        # Breakfast specific
        'breakfast entrees': 95,
        'breakfast sandwiches': 90,
        'breakfast sides': 75,
        'eggs': 85,
        'omelets': 85,
        'pancakes': 85,
        'waffles': 85,
        
        # Beverages
        'drinks': 70,
        'beverages': 70,
        'coffee': 70,
        'tea': 70,
        'smoothies': 70,
        
        # Secondary categories
        'toppings': 50,
        'add ons': 40,
        'add-ons': 40,
        'extras': 40,
        'condiments': 35,
        'dressings': 35,
        'sauces': 35,
        
        # Build your own / customization
        'build your own': 60,
        'customize': 60,
        'create your own': 60,
        
        # Generic/fallback categories
        'menu': 20,
        'items': 15,
        'general': 10,
        'other': 10,
    }
    
    def get_section_priority(section: str) -> int:
        """Get priority score for a section, with improved matching."""
        section_lower = section.lower()
        
        # Exact match first
        if section_lower in section_priorities:
            return section_priorities[section_lower]
        
        # Check for compound sections (e.g., "Hot Breakfast Sandwiches")
        # Give bonus points for more specific descriptions
        base_priority = 0
        bonus_points = 0
        
        # Check each known section type
        for key, priority in section_priorities.items():
            if key in section_lower:
                base_priority = max(base_priority, priority)
                
        # Add bonus points for specificity
        specificity_keywords = ['hot', 'cold', 'fresh', 'house', 'special', 'signature', 'premium']
        bonus_points += sum(5 for keyword in specificity_keywords if keyword in section_lower)
        
        # Add bonus for longer, more descriptive names (but cap it)
        length_bonus = min(len(section.split()) * 2, 10)  # Up to 10 points for length
        bonus_points += length_bonus
        
        if base_priority > 0:
            return base_priority + bonus_points
        
        # Default priority for unknown sections
        return 15 + bonus_points  # Higher base priority for unknown sections
    
    current_priority = get_section_priority(current_section)
    new_priority = get_section_priority(new_section)
    
    # If priorities are close, prefer keeping the current section
    # This prevents unnecessary section changes
    PRIORITY_THRESHOLD = 10
    if abs(new_priority - current_priority) <= PRIORITY_THRESHOLD:
        return False
    
    return new_priority > current_priority


def _gather_items_from_page(page) -> List[Tuple[str, str]]:
    """Extract (itemID, name) pairs from the current DOM."""
    # Enhanced item detection with multiple strategies
    items = []
    
    # Strategy 1: Original selector
    items.extend(page.evaluate(
        r"""
        () => Array.from(document.querySelectorAll('a.cbo_nn_itemHover')).map(el => {
            const rawAttr = el.dataset.itemid || el.getAttribute('data-itemid') || '';
            const onclick = el.getAttribute('onclick') || '';
            const idMatch = rawAttr || (onclick.match(/\d+/) || [])[0];
            return [idMatch, el.textContent.trim()];
        });
        """
    ))
    
    # Strategy 2: Look for items with nutrition onclick handlers
    items.extend(page.evaluate(
        r"""
        () => Array.from(document.querySelectorAll('a[onclick*="nutrition"], a[onclick*="showLabel"]')).map(el => {
            const onclick = el.getAttribute('onclick') || '';
            const idMatch = (onclick.match(/\d+/) || [])[0];
            return [idMatch, el.textContent.trim()];
        });
        """
    ))
    
    # Strategy 3: Look for items in menu panels
    items.extend(page.evaluate(
        r"""
        () => {
            const menuItems = [];
            ['#itemPanel', '#menuList', '.menu-items'].forEach(container => {
                const links = document.querySelectorAll(`${container} a[onclick]`);
                links.forEach(el => {
                    const onclick = el.getAttribute('onclick') || '';
                    if (onclick.includes('nutrition') || onclick.includes('showLabel')) {
                        const idMatch = (onclick.match(/\d+/) || [])[0];
                        menuItems.push([idMatch, el.textContent.trim()]);
                    }
                });
            });
            return menuItems;
        }
        """
    ))
    
    # Filter and deduplicate items
    seen_ids = set()
    filtered_items = []
    for item_id, name in items:
        if not item_id or not name:
            continue
            
        # Skip UI elements and non-food items
        skip_words = ['click', 'view', 'more', 'details', 'info', 'nutrition', 'allergen']
        if any(word in name.lower() for word in skip_words):
            continue
            
        # Use item ID for deduplication
        if item_id not in seen_ids:
            seen_ids.add(item_id)
            filtered_items.append((item_id, name))
    
    return filtered_items


def determine_actual_meal_period(meal_period_name: str, restaurant_name: str, page_context: str = "") -> str:
    """Determine the actual meal period based on multiple context clues."""
    meal_period_lower = meal_period_name.lower()
    restaurant_lower = restaurant_name.lower()
    context_lower = page_context.lower()
    
    # Direct mapping for clear cases
    direct_mappings = {
        'breakfast': 'Breakfast',
        'lunch': 'Lunch', 
        'dinner': 'Dinner',
        'brunch': 'Brunch',
        'late night': 'Late Night',
        'all day': 'All Day'
    }
    
    # Check for direct matches first
    for key, value in direct_mappings.items():
        if key in meal_period_lower:
            return value
    
    # Handle combined periods
    if any(phrase in meal_period_lower for phrase in ['lunch and dinner', 'lunch & dinner', 'lunch/dinner']):
        return 'Lunch/Dinner'
    
    # Restaurant-specific logic
    if 'indian' in restaurant_lower or 'tandoor' in restaurant_lower:
        # Indian restaurants often serve the same items for lunch and dinner
        if meal_period_lower in ['lunch', 'dinner']:
            return 'Lunch/Dinner'
    
    if 'cafe' in restaurant_lower or 'coffee' in restaurant_lower:
        # Cafes often serve items all day
        return 'All Day'
    
    # Check page context for time indicators
    time_indicators = {
        'breakfast': ['6:', '7:', '8:', '9:', '10:', 'morning', 'am'],
        'lunch': ['11:', '12:', '1:', '2:', '3:', 'afternoon', 'noon'],
        'dinner': ['4:', '5:', '6:', '7:', '8:', '9:', 'evening', 'night']
    }
    
    for period, indicators in time_indicators.items():
        if any(indicator in context_lower for indicator in indicators):
            return period.title()
    
    # Default based on common patterns
    if 'combo' in meal_period_lower or 'meal' in meal_period_lower:
        return 'All Day'
    
    # Fallback
    return meal_period_name


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
        text_links = page.locator("a:has-text('Breakfast'), a:has-text('All Day'), a:has-text('Specialty'), a:has-text('Lunch'), a:has-text('Dinner'), a:has-text('Lunch and Dinner'), a:has-text('Combo'), a:has-text('Brunch'), a:has-text('Late Night')").all()
        
        # Strategy 2: Also look for any links with data-mealoid attribute (broader search)
        mealoid_links = page.locator("a[data-mealoid]").all()
        
        # Strategy 3: Look for menu tabs that might indicate meal periods
        menu_tabs = page.locator("a.cbo_nn_menuLink").all()
        
        # Combine all strategies
        all_potential_links = text_links + mealoid_links + menu_tabs
        
        # Filter to only include links that have proper meal period attributes
        seen_meal_ids = set()
        for link in all_potential_links:
            try:
                text = link.text_content().strip()
                meal_id = link.get_attribute("data-mealoid")
                
                # Skip if we've already seen this meal ID or if it's invalid
                if not meal_id or meal_id in seen_meal_ids or meal_id == "-1":
                    continue
                
                # Enhanced meal period detection
                meal_keywords = {
                    'breakfast': ['breakfast', 'morning', 'early bird'],
                    'lunch': ['lunch', 'afternoon', 'midday'],
                    'dinner': ['dinner', 'evening', 'night'],
                    'brunch': ['brunch'],
                    'late night': ['late night', 'late dining', 'after hours'],
                    'all day': ['all day', 'anytime', '24/7'],
                    'specialty': ['specialty', 'special', 'featured'],
                    'combo': ['combo', 'combination', 'meal deal']
                }
                
                text_lower = text.lower()
                
                # Check for meal period keywords
                is_meal_period = False
                for period, keywords in meal_keywords.items():
                    if any(keyword in text_lower for keyword in keywords):
                        is_meal_period = True
                        break
                
                # Additional validation for non-keyword matches
                if not is_meal_period:
                    # Check if it looks like a valid menu section
                    # Exclude common non-meal-period text
                    non_meal_words = ['click here', 'details', 'nutrition', 'allergen', 'ingredients']
                    if not any(word in text_lower for word in non_meal_words):
                        # Include if text length is reasonable and has meal ID
                        if meal_id and 2 < len(text) < 50:
                            is_meal_period = True
                
                if is_meal_period:
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
                    
                    # Get the meal ID and unit ID
                    meal_id = meal_period.get_attribute("data-mealoid")
                    unit_id = meal_period.get_attribute("data-unitoid") 
                    
                    # Get page context for better meal period determination
                    try:
                        page_context = page.evaluate("""
                            () => {
                                const titleElement = document.querySelector('.cbo_nn_menuHeaderTitle');
                                const timeElement = document.querySelector('.time-info');
                                return {
                                    title: titleElement ? titleElement.textContent : '',
                                    time: timeElement ? timeElement.textContent : '',
                                    url: window.location.href
                                };
                            }
                        """)
                        context_text = f"{page_context.get('title', '')} {page_context.get('time', '')}"
                    except Exception:
                        context_text = ""
                    
                    # Use improved meal period determination
                    actual_meal_period = determine_actual_meal_period(meal_period_name, unit_name, context_text)
                    
                    print(f"  Mapped meal period '{meal_period_name}' to '{actual_meal_period}'")

                    try:
                        # First, click the menu button to show the dropdown
                        page.evaluate("""
                            () => {
                                const button = document.querySelector('#nav-meal-selector button');
                                if (button) {
                                    button.click();
                                    // Also ensure dropdown is shown
                                    const dropdown = document.querySelector('#nav-meal-selector');
                                    if (dropdown) {
                                        dropdown.classList.add('show');
                                        const menu = dropdown.querySelector('.dropdown-menu');
                                        if (menu) {
                                            menu.classList.add('show');
                                            menu.style.display = 'block';
                                        }
                                    }
                                }
                            }
                        """)
                        time.sleep(1)  # Give dropdown time to open
                        
                        # Now click the meal period link
                        page.evaluate(f"""
                            () => {{
                                const link = document.querySelector('a[data-mealoid="{meal_id}"]');
                                if (link) {{
                                    // Create and dispatch click event
                                    const clickEvent = new MouseEvent('click', {{
                                        bubbles: true,
                                        cancelable: true,
                                        view: window
                                    }});
                                    link.dispatchEvent(clickEvent);
                                    
                                    // Also try the onclick handler directly
                                    const onclick = link.getAttribute('onclick');
                                    if (onclick && onclick.includes('handleNavBarSelection')) {{
                                        window.NetNutrition.UI.handleNavBarSelection(link);
                                    }}
                                }}
                            }}
                        """)
                        
                        # Wait for content to load
                        time.sleep(2)
                        
                        # Try to find and click menu items
                        items_found = page.evaluate("""
                            () => {
                                // Make all containers visible
                                ['#itemPanel', '#menuList', '#cbo_nn_menuListContainer'].forEach(selector => {
                                    const container = document.querySelector(selector);
                                    if (container) {
                                        container.style.display = 'block';
                                        container.style.visibility = 'visible';
                                        container.classList.remove('d-none');
                                    }
                                });
                                
                                // Find all links with onclick handlers
                                const links = Array.from(document.querySelectorAll('a[onclick]'));
                                const menuItems = links.filter(link => {
                                    const onclick = link.getAttribute('onclick');
                                    return onclick && (
                                        onclick.includes('showLabel') ||
                                        onclick.includes('getItemNutritionLabel') ||
                                        onclick.includes('menuListSelectMenu')
                                    );
                                });
                                
                                // Try to click each menu item
                                menuItems.forEach(item => {
                                    try {
                                        // Create and dispatch click event
                                        const clickEvent = new MouseEvent('click', {
                                            bubbles: true,
                                            cancelable: true,
                                            view: window
                                        });
                                        item.dispatchEvent(clickEvent);
                                        
                                        // Also try the onclick handler directly
                                        const onclick = item.getAttribute('onclick');
                                        if (onclick) {
                                            // Extract function name and arguments
                                            const match = onclick.match(/(\w+)\((.*?)\)/);
                                            if (match) {
                                                const [_, func, args] = match;
                                                if (window.NetNutrition && window.NetNutrition.UI && window.NetNutrition.UI[func]) {
                                                    window.NetNutrition.UI[func].apply(window.NetNutrition.UI, args.split(','));
                                                }
                                            }
                                        }
                                    } catch (e) {
                                        console.error('Failed to click menu item:', e);
                                    }
                                });
                                
                                return {
                                    menuItems: menuItems.length,
                                    itemHover: document.querySelectorAll('.cbo_nn_itemHover').length,
                                    showLabel: document.querySelectorAll('a[onclick*="showLabel"]').length,
                                    menuList: document.querySelectorAll('#menuList .cbo_nn_menuList').length,
                                    tableRows: document.querySelectorAll('#itemPanel table tbody tr').length,
                                    onclickLinks: links.length
                                };
                            }
                        """)
                        
                        print(f"  Found items: {items_found}")
                        
                    except Exception as e:
                        print(f"  Failed to select meal period via JavaScript: {e}")
                        continue
                    
                    # Process items in this meal period with section detection
                    sections = page.locator("#itemPanel table tbody tr").all()
                    current_section = "General"
                    
                    # DEBUG: Let's see the actual HTML structure
                    print(f"  [DEBUG] Found {len(sections)} rows in itemPanel")
                    
                    # First, expand all collapsed sections to make items visible
                    try:
                        expanded_count = page.evaluate("""
                            () => {
                                let count = 0;
                                // Look for collapse buttons and click them to expand sections
                                const collapseButtons = document.querySelectorAll('.js-collapse-icon, [role="button"]:has(.fa-caret-right), .cbo_nn_menuList');
                                collapseButtons.forEach(button => {
                                    try {
                                        // Check if it's collapsed (has caret-right)
                                        if (button.classList.contains('fa-caret-right') || 
                                            button.querySelector('.fa-caret-right') ||
                                            button.textContent.includes('►')) {
                                            button.click();
                                            count++;
                                        }
                                    } catch (e) {
                                        // Ignore click errors
                                    }
                                });
                                
                                // Also try to expand via the parent elements
                                const expandableRows = document.querySelectorAll('#itemPanel table tbody tr td[colspan] div[role="button"]');
                                expandableRows.forEach(row => {
                                    try {
                                        row.click();
                                        count++;
                                    } catch (e) {
                                        // Ignore click errors
                                    }
                                });
                                
                                return count;
                            }
                        """)
                        if expanded_count > 0:
                            print(f"  → Expanded {expanded_count} collapsed sections")
                            page.wait_for_load_state("networkidle", timeout=3000)
                            time.sleep(1)
                            
                            # Refresh the sections list after expansion
                            sections = page.locator("#itemPanel table tbody tr").all()
                            print(f"  → Now found {len(sections)} rows after expansion")
                    except Exception as e:
                        print(f"  → Failed to expand sections: {e}")

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
                                    
                                    # Create unique key that ALWAYS includes section to allow same items in different sections
                                    # Always include section to handle cases where same item ID appears in multiple sections
                                    unique_key = f"{food_name}_{unit_name}_{actual_meal_period}_{current_section}"
                                    
                                    # Check if we've seen this item before - but only skip if it's truly the same item in the same context
                                    if unique_key in processed_names:
                                        stored_item = processed_names[unique_key]
                                        # Since unique_key now includes section, this should only happen if it's truly the same item
                                        print(f"  Skipping exact duplicate: {food_name} in section '{current_section}' (already processed)")
                                        continue
                                    
                                    # Store item info for future section comparisons
                                    processed_names[unique_key] = {
                                        'section': current_section,
                                        'meal_period': actual_meal_period,
                                        'name': food_name
                                    }
                                    
                                    # Extract nutrition data
                                    nutrition_data = extract_nutrition_from_item(page, food_item, food_name, unit_name, actual_meal_period)
                                    all_items_nutrition.append((food_name, unit_name, actual_meal_period, current_section, nutrition_data))
                                    
                                except Exception as e:
                                    print(f"  [!] Failed to process food item: {e}")
                                    
                        except Exception as e:
                            print(f"  [!] Failed to process section row: {e}")
                    
                    meal_items = [item for item in all_items_nutrition if item[2] == actual_meal_period]
                    print(f"  Completed {actual_meal_period}: found {len(meal_items)} items")
                    
                except Exception as e:
                    print(f"[!] Failed to process meal period {actual_meal_period}: {e}")
            
            # For restaurants with many meal periods but same items, default to "All Day"
            if all_items_nutrition:
                # Deduplicate while allowing same item name in different sections
                seen_items = {}  # key: (item_name, section) to allow duplicates across sections
                unique_items = []

                for item in all_items_nutrition:
                    item_name, restaurant, meal_period, section, nutrition = item

                    key = (item_name, section)

                    # If we haven't seen this item in this section before, add it directly
                    if key not in seen_items:
                        seen_items[key] = meal_period  # store meal period for potential priority logic
                        unique_items.append(item)
                    else:
                        # If we have same item in same section but different meal periods,
                        # prefer the one that is not 'All Day'
                        prev_meal_period = seen_items[key]
                        if prev_meal_period == 'All Day' and meal_period != 'All Day':
                            # Replace previous entry with more specific meal period
                            for i, prev_item in enumerate(unique_items):
                                if prev_item[0] == item_name and prev_item[3] == section:
                                    unique_items[i] = item
                                    seen_items[key] = meal_period
                                    break

                all_items_nutrition = unique_items
                print(f"Successfully extracted {len(all_items_nutrition)} items using meal period approach")
        
        # Fallback: Use standard approach if no meal periods or meal period approach failed
        if not meal_period_links or not all_items_nutrition:
            print(f"Using standard approach for {unit_name}...")
            
            # Standard approach - works for restaurants without meal periods
            try:
                meal_tabs = page.locator("a.cbo_nn_menuLink").all()
                print(f"Found {len(meal_tabs)} menu tabs")
                
                tabs_to_process = [None] + meal_tabs  # None represents the initial state

                for meal_tab in tabs_to_process:
                    if meal_tab:
                        try:
                            # Try clicking with reduced timeout
                            meal_tab.click(timeout=5000)
                            page.wait_for_load_state("networkidle", timeout=5000)
                            time.sleep(0.8)
                        except Exception as e:
                            print(f"[!] Failed to process meal tab (trying JavaScript click): {e}")
                            try:
                                # Fallback to JavaScript click
                                tab_id = meal_tab.get_attribute("id")
                                if tab_id:
                                    page.evaluate(f'document.getElementById("{tab_id}").click()')
                                    page.wait_for_load_state("networkidle", timeout=5000)
                                    time.sleep(0.8)
                            except Exception as e2:
                                print(f"[!] JavaScript click also failed: {e2}")
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
                                
                                # Create unique key that ALWAYS includes section to allow same items in different sections
                                # Always include section to handle cases where same item ID appears in multiple sections
                                unique_key = f"{food_name}_{unit_name}_All Day_{current_section}"
                                
                                # Check if we've seen this item before - but only skip if it's truly the same item in the same context
                                if unique_key in processed_names:
                                    stored_item = processed_names[unique_key]
                                    # Since unique_key now includes section, this should only happen if it's truly the same item
                                    print(f"  Skipping exact duplicate: {food_name} in section '{current_section}' (already processed)")
                                    continue
                                else:
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

            except Exception as e:
                print(f"  [!] Failed to process meal tab: {e}")

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
    
    # Get item ID first - we'll need this for several approaches
    item_id = None
    onclick = food_item.get_attribute("onclick") or ""
    
    # Try multiple patterns to extract item ID
    id_patterns = [
        r'getItemNutritionLabelOnClick\(event,(\d+)\)',
        r'showLabel\((\d+)\)',
        r'getItemNutritionLabel\((\d+)\)',
        r'data-itemid="(\d+)"',
        r'itemid=(\d+)',
        r'item_id=(\d+)',
        r'(\d{4,})'  # Look for any 4+ digit number as last resort
    ]
    
    for pattern in id_patterns:
        match = re.search(pattern, onclick)
        if match:
            item_id = match.group(1)
            break
    
    # Also try data-itemid attribute directly
    if not item_id:
        item_id = food_item.get_attribute("data-itemid")
    
    # If we found an item ID, try the direct API approach first
    if item_id:
        try:
            # Construct the nutrition endpoint URL
            nutrition_url = NUTRITION_ENDPOINT.format(item_id=item_id)
            
            # Add headers to mimic browser request
            headers = {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': BASE_URL,
                'Connection': 'keep-alive',
            }
            
            # Make the request with headers and session cookies from the page
            cookies = page.context.cookies()
            cookie_dict = {cookie['name']: cookie['value'] for cookie in cookies}
            
            response = requests.get(
                nutrition_url,
                headers=headers,
                cookies=cookie_dict,
                timeout=10
            )
            
            if response.status_code == 200 and response.text.strip():
                nutrition_data = parse_nutrition_html(response.text)
                if nutrition_data["calories"] > 0:
                    clicked = True
                    print(f"  → Used direct API call for {food_name}")
                    return nutrition_data
                else:
                    print(f"  → API returned no calories for {food_name}, trying UI methods")
            else:
                print(f"  → API returned status {response.status_code} or empty response for {food_name}")
        except Exception as e:
            print(f"  → Direct API call failed: {e}")
    
    # If API call failed, try JavaScript-based nutrition function call
    if not clicked and item_id:
        try:
            # Try calling the nutrition function directly via JavaScript
            success = page.evaluate(f"""
                () => {{
                    try {{
                        // Try different approaches to get nutrition data
                        if (window.NetNutrition && window.NetNutrition.UI) {{
                            // Method 1: Direct function call
                            if (window.NetNutrition.UI.getItemNutritionLabel) {{
                                window.NetNutrition.UI.getItemNutritionLabel({item_id});
                                return true;
                            }}
                            
                            // Method 2: Call with mock event
                            if (window.NetNutrition.UI.getItemNutritionLabelOnClick) {{
                                const mockEvent = {{
                                    target: document.getElementById('showNutrition_{item_id}') || document.body,
                                    preventDefault: () => {{}},
                                    stopPropagation: () => {{}}
                                }};
                                window.NetNutrition.UI.getItemNutritionLabelOnClick(mockEvent, {item_id});
                                return true;
                            }}
                        }}
                        
                        return false;
                    }} catch (e) {{
                        console.error('JavaScript nutrition call failed:', e);
                        return false;
                    }}
                }}
            """)
            
            if success:
                clicked = True
                print(f"  → Used JavaScript nutrition function for {food_name}")
        except Exception as e:
            print(f"  → JavaScript nutrition function failed: {e}")
    
    # If still no success, try to make the element visible and clickable
    if not clicked:
        try:
            # Use JavaScript to make element visible and click it
            success = page.evaluate("""
                (element) => {
                    try {
                        // Make element and its parents visible
                        let current = element;
                        while (current) {
                            if (current.style) {
                                current.style.display = 'block';
                                current.style.visibility = 'visible';
                                current.style.opacity = '1';
                                current.style.position = 'static';
                                current.style.zIndex = '9999';
                            }
                            if (current.classList) {
                                current.classList.remove('d-none', 'hidden');
                            }
                            current = current.parentElement;
                        }
                        
                        // Scroll element into view
                        element.scrollIntoView({behavior: 'instant', block: 'center'});
                        
                        // Wait a bit for any animations
                        setTimeout(() => {
                            // Try multiple click methods
                            try {
                                element.click();
                            } catch (e1) {
                                try {
                                    const event = new MouseEvent('click', {
                                        bubbles: true,
                                        cancelable: true,
                                        view: window
                                    });
                                    element.dispatchEvent(event);
                                } catch (e2) {
                                    // Try executing onclick directly
                                    const onclick = element.getAttribute('onclick');
                                    if (onclick) {
                                        eval(onclick.replace('javascript:', ''));
                                    }
                                }
                            }
                        }, 100);
                        
                        return true;
                    } catch (e) {
                        console.error('Force visibility click failed:', e);
                        return false;
                    }
                }
            """, food_item)
            
            if success:
                clicked = True
                print(f"  → Used force visibility click for {food_name}")
                time.sleep(0.5)  # Give time for the nutrition popup to appear
        except Exception as e:
            print(f"  → Force visibility click failed: {e}")
    
    # If we managed to trigger something, try to extract nutrition data
    if clicked:
        try:
            # Wait for nutrition popup with increased timeout and multiple selectors
            nutrition_content = None
            selectors = [
                "#nutritionLabel",
                ".cbo_nn_nutritionLabel", 
                "[id*='nutrition']",
                ".nutrition-label",
                "#nutrition-facts",
                ".nutrition-popup",
                "[class*='nutrition']"
            ]
            
            # Try each selector with longer wait times
            for selector in selectors:
                try:
                    element = page.wait_for_selector(selector, timeout=8000)
                    if element and element.is_visible():
                        nutrition_content = element.inner_html()
                        if nutrition_content and len(nutrition_content.strip()) > 50:  # Make sure we got substantial content
                            break
                except Exception:
                    continue
            
            if nutrition_content:
                nutrition_data = parse_nutrition_html(nutrition_content)
                
                if nutrition_data["calories"] > 0:
                    print(f"✓ Extracted {food_name} from {restaurant_name} ({meal_period}) - {nutrition_data['calories']} cal")
                else:
                    print(f"⚠ No calories found in nutrition data for {food_name}")
                    
                    # Try one more time to get any nutrition content from the page
                    try:
                        # Look for nutrition info anywhere on the page
                        all_text = page.locator("body").inner_text()
                        
                        # Try to find calories in the page text
                        calories_patterns = [
                            r'Calories[:\s]*(\d+)',
                            r'(\d+)\s*calories',
                            r'Cal[:\s]*(\d+)'
                        ]
                        
                        for pattern in calories_patterns:
                            match = re.search(pattern, all_text, re.IGNORECASE)
                            if match:
                                nutrition_data["calories"] = int(match.group(1))
                                print(f"  → Found calories in page text: {nutrition_data['calories']}")
                                break
                    except Exception as e:
                        print(f"  → Failed to find calories in page text: {e}")
            else:
                print(f"⚠ No nutrition content found for {food_name}")
            
            # Close any open popups more aggressively
            try:
                # Try multiple approaches to close popups
                close_attempts = [
                    lambda: page.keyboard.press("Escape"),
                    lambda: page.locator("#btn_nn_nutrition_close").click(timeout=2000),
                    lambda: page.locator(".close").first.click(timeout=2000),
                    lambda: page.locator("button:has-text('Close')").click(timeout=2000),
                    lambda: page.locator("[aria-label='Close']").click(timeout=2000)
                ]
                
                for attempt in close_attempts:
                    try:
                        attempt()
                        page.wait_for_load_state("networkidle", timeout=3000)
                        break
                    except:
                        continue
            except Exception:
                pass
            
        except Exception as e:
            print(f"[!] Failed to extract nutrition data for {food_name}: {e}")
            # Try to close any open popup
            try:
                page.keyboard.press("Escape")
            except:
                pass
    else:
        print(f"⚠ Could not interact with {food_name} - skipping nutrition extraction")
    
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
    # Track unique combinations to avoid duplicates while allowing same name in different sections
    seen_items = set()
    
    for name, restaurant, meal_period, section, nutrition in items_nutrition:
        try:
            # Create unique key that includes section to allow duplicates across sections
            unique_key = f"{name}_{restaurant}_{meal_period}_{section}"
            
            # Skip if we've seen this exact combination before
            if unique_key in seen_items:
                continue
                
            seen_items.add(unique_key)
            
            # Store all entries as single rows, including combined meal periods
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
                print(f"✓ Stored {name} ({section}) - {nutrition['calories']} cal")
                
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