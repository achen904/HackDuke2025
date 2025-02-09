import sqlite3

conn = sqlite3.connect("dummy1.db")
cursor = conn.cursor()
cursor.execute("SELECT * from items")
data = cursor.fetchall()
print(data)