import sqlite3

connection = sqlite3.connect("face_database.db")

cursor = connection.cursor()

cursor.execute("""
    CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id TEXT UNIQUE NOT NULL,
        embedding BLOB NOT NULL
    )
""")

connection.commit()
connection.close()

print("Face database created successfully!")