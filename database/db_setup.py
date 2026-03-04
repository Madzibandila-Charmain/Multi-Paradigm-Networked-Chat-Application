# Ranwashe Mukovhe - Database table creation
# This creates the SQLite database file and all the tables 
# The database is stored as a single file: ChatApp.db

import sqlite3
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import DB_NAME

from database.db_manager import (
    register_user, verify_user, set_user_status,
    save_message, get_offline_messages, mark_delivered,
    create_group, add_to_group, remove_from_group,
    get_group_members, block_user, is_blocked
)

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

def test_database():
    """
    Tests all the main database functions to confirm everything works.
    Run this once after create_tables() to verify the database is ready.
    """
    print("\n[TEST] Starting database tests...")

    # Test register and verify user
    register_user("test_user", "test123")
    assert verify_user("test_user", "test123") == True, "verify_user failed"
    assert verify_user("test_user", "wrongpassword") == False, "verify_user should return False"
    print("[TEST] register_user and verify_user passed")

    # Test set_user_status
    set_user_status("test_user", "online")
    print("[TEST] set_user_status passed")

    # Test save and retrieve offline messages
    save_message("mukovhe", "test_user", "TEXT", "hello", "2026-03-03T10:00:00")
    messages = get_offline_messages("test_user")
    assert len(messages) > 0, "get_offline_messages failed"
    print("[TEST] save_message and get_offline_messages passed")

    # Test mark_delivered
    mark_delivered(messages[0]["message_id"])
    print("[TEST] mark_delivered passed")

    # Test group functions
    create_group("test_group", "test_user")
    add_to_group("test_group", "mukovhe")
    members = get_group_members("test_group")
    assert "mukovhe" in members, "add_to_group failed"
    remove_from_group("test_group", "mukovhe")
    print("[TEST] Group functions passed")

    # Test block functions
    block_user("test_user", "mukovhe")
    assert is_blocked("test_user", "mukovhe") == True, "is_blocked failed"
    assert is_blocked("test_user", "charmain") == False, "is_blocked should return False"
    print("[TEST] block_user and is_blocked passed")

    print("\n[TEST] All tests passed - database is ready")


if __name__ == "__main__":
    create_tables()
    register_user("mukovhe", "password123")
    register_user("charmain", "password123")
    register_user("konke", "password123")
    register_user("yashil", "password123")
    register_user("mumi", "password123")
    print("\n[DB] Test users registered")
    test_database()