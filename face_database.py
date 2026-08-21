import sqlite3

#------ connection to db
connection = sqlite3.connect("students.db")

#cursor
cursor = connection.cursor()

#table
cursor.execute("""
    CREATE TABLE IF NOT EXISTS students(
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               name TEXT NOT NULL,
               embedding BLOB NOT NULL
               )              
               """)

# save
connection.commit()

#close
connection.close()

print("Datababe created successfully!")