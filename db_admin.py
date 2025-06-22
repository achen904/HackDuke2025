#!/usr/bin/env python3
"""
Database Administration Utilities for Duke Nutrition Database

This module contains developer-only utilities for managing the database.
These functions should NOT be accessible to the AI agent.
"""

import os
import sqlite3
from typing import Optional


def delete_database(db_file: str = "duke_nutrition.db") -> str:
    """Delete the specified SQLite database file.

    Parameters
    ----------
    db_file : str
        Path to the SQLite database file. Defaults to "duke_nutrition.db".
        
    Returns
    -------
    str
        Status message indicating success or failure.
    """
    try:
        os.remove(db_file)
        return f"✅ Deleted database file: {db_file}"
    except FileNotFoundError:
        return f"❌ Database file not found: {db_file}"
    except Exception as e:
        return f"❌ Error deleting database file: {e}"


def create_database(db_file: str = "duke_nutrition.db") -> str:
    """Create a new SQLite database file (or open if it exists).
    
    Parameters
    ----------
    db_file : str
        Path to the SQLite database file. Defaults to "duke_nutrition.db".
        
    Returns
    -------
    str
        Status message indicating success or failure.
    """
    try:
        conn = sqlite3.connect(db_file)
        conn.close()
        return f"✅ Database created or opened successfully: {db_file}"
    except Exception as e:
        return f"❌ Error creating database: {e}"


def clear_items(db_file: str = "duke_nutrition.db") -> str:
    """Delete all rows from the `items` table while keeping the database file intact.

    This is useful when you want to preserve the schema but repopulate the table
    with fresh data using the scraper. Also resets the autoincrement ID back to 1.
    
    Parameters
    ----------
    db_file : str
        Path to the SQLite database file. Defaults to "duke_nutrition.db".
        
    Returns
    -------
    str
        Status message with details about the operation.
    """
    try:
        conn = sqlite3.connect(db_file)
        cur = conn.cursor()
        cur.execute("DELETE FROM items")
        deleted = cur.rowcount  # -1 means undetermined for SQLite
        
        # Reset the autoincrement sequence so next insert starts at id=1
        cur.execute("DELETE FROM sqlite_sequence WHERE name='items'")
        
        conn.commit()
        conn.close()
        
        msg = (
            f"✅ Cleared {deleted if deleted != -1 else 'all'} rows from 'items' table in {db_file}. "
            f"ID sequence reset to start from 1."
        )
        return msg
    except sqlite3.OperationalError as e:
        # Likely the table does not exist yet
        return f"❌ Error: {e}. Make sure the 'items' table exists before clearing."
    except Exception as e:
        return f"❌ Unexpected error clearing items: {e}"


def get_database_stats(db_file: str = "duke_nutrition.db") -> str:
    """Get statistics about the database contents.
    
    Parameters
    ----------
    db_file : str
        Path to the SQLite database file. Defaults to "duke_nutrition.db".
        
    Returns
    -------
    str
        Formatted statistics about the database.
    """
    try:
        conn = sqlite3.connect(db_file)
        cursor = conn.cursor()
        
        # Get total item count
        cursor.execute("SELECT COUNT(*) FROM items")
        total_items = cursor.fetchone()[0]
        
        # Get count by restaurant
        cursor.execute("SELECT restaurant, COUNT(*) FROM items GROUP BY restaurant ORDER BY COUNT(*) DESC")
        restaurant_counts = cursor.fetchall()
        
        # Get items with nutrition data
        cursor.execute("SELECT COUNT(*) FROM items WHERE calories IS NOT NULL")
        items_with_nutrition = cursor.fetchone()[0]
        
        conn.close()
        
        result = f"""
📊 Database Statistics for {db_file}:
━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

📋 Total Items: {total_items}
🍽️  Items with Nutrition Data: {items_with_nutrition}
📈 Coverage: {(items_with_nutrition/total_items*100):.1f}%

🏪 Items by Restaurant:
"""
        
        for restaurant, count in restaurant_counts:
            result += f"   • {restaurant}: {count} items\n"
            
        return result.strip()
        
    except Exception as e:
        return f"❌ Error getting database stats: {e}"


def main():
    """Command-line interface for database administration."""
    import sys
    
    if len(sys.argv) < 2:
        print("""
🔧 Duke Nutrition Database Administration

Usage: python db_admin.py <command> [options]

Commands:
  stats                    - Show database statistics
  clear                    - Clear all items from database
  delete [filename]        - Delete database file
  create [filename]        - Create new database file

Examples:
  python db_admin.py stats
  python db_admin.py clear
  python db_admin.py delete duke_nutrition.db
  python db_admin.py create new_database.db
        """)
        return
    
    command = sys.argv[1].lower()
    db_file = sys.argv[2] if len(sys.argv) > 2 else "duke_nutrition.db"
    
    if command == "stats":
        print(get_database_stats(db_file))
    elif command == "clear":
        response = input(f"⚠️  Are you sure you want to clear all items from {db_file}? (yes/no): ")
        if response.lower() == "yes":
            print(clear_items(db_file))
        else:
            print("❌ Operation cancelled.")
    elif command == "delete":
        response = input(f"⚠️  Are you sure you want to DELETE {db_file}? This cannot be undone! (yes/no): ")
        if response.lower() == "yes":
            print(delete_database(db_file))
        else:
            print("❌ Operation cancelled.")
    elif command == "create":
        print(create_database(db_file))
    else:
        print(f"❌ Unknown command: {command}")
        print("Use 'python db_admin.py' without arguments to see available commands.")


if __name__ == "__main__":
    main() 