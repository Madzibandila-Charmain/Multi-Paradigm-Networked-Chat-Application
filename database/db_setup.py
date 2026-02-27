# CSC3002F - Multi-Paradigm Chat Application
# MUKOVHE - Database table creation
# This creates the SQLite database file and all the tables 
# The database is stored as a single file: ChatApp.db

import sqlite3
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import DB_NAME

def create_tables():
    """
    Connect to the database and create all the required tables.
    SQLite creates the .db file automatically if it doesn't exist.
    If NOT EXSISTS it means that running this twice will not cause errors
    """

    # Connect to (or create) the database file
    connection = sqlite3.connect(DB_NAME)

    # Cursor used to execute SQL statements
    cursor = connection.cursor()

    # Users table which stores and registers user accounts and stores statuses
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id       INTEGER PRIMARY KEY AUTOINCREMENT,
            username      TEXT    NOT NULL UNIQUE,
            password_hash TEXT    NOT NULL,
            status        TEXT    NOT NULL DEFAULT 'offline'
        )
    """)
    print("[DB] Table 'users' ready")