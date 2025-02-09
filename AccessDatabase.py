import sqlite3

conn = sqlite3.connect("duke_nutrition.db")
cursor = conn.cursor()
cursor.execute("SELECT * from items")
data = cursor.fetchall()
print(data)