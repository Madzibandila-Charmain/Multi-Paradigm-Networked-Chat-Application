# Ranwashe Mukovhe - Database table creation
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
    If NOT EXISTS it means that running this twice will not cause errors
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

    # Stores messages for offline delivery (store-and-forward)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            message_id  INTEGER PRIMARY KEY AUTOINCREMENT,
            sender      TEXT    NOT NULL,
            receiver    TEXT    NOT NULL,
            msg_type    TEXT    NOT NULL,
            content     TEXT,
            timestamp   TEXT    NOT NULL,
            delivered   INTEGER NOT NULL DEFAULT 0
        )
    """)
    print("[DB] Table 'messages' ready")

    # Stores group chats
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS groups (
            group_id    INTEGER PRIMARY KEY AUTOINCREMENT,
            group_name  TEXT    NOT NULL UNIQUE,
            created_by  TEXT    NOT NULL
        )
    """)
    print("[DB] Table 'groups' ready")

    # Maps users to groups - composite primary key prevents duplicates
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS group_members (
            group_name  TEXT NOT NULL,
            username    TEXT NOT NULL,
            PRIMARY KEY (group_name, username)
        )
    """)
    print("[DB] Table 'group_members' ready")

    # Stores which users have blocked which other users
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS blocked_users (
            user_id         TEXT NOT NULL,
            blocked_user_id TEXT NOT NULL,
            PRIMARY KEY (user_id, blocked_user_id)
        )
    """)
    print("[DB] Table 'blocked_users' ready")

if __name__ == "__main__":
    create_tables()