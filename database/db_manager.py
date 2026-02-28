# CSC3002F - Multi-Paradigm Chat Application
# All database read/write functions
# The server calls these functions - it never accesses the database directly

import sqlite3
import hashlib
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import DB_NAME

def get_connection():
    """
    Opena and reutrns a connection to the database.
    check_same_thread=False is requiredbecuase multiple server threads will call these functions at the same time.
    """
    return sqlite3.connect(DB_NAME, check_same_thread=False)

def hash_password(password):
    """
    we hash the password before storing it so plain text passwords are never in the database
    We never store plain text passwords in the database.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def register_user(username, password):
    """
    Register a new user account with a hashed password.
    Returns True is registration successful and False if the username already exixts.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, hashed_password) VALUES (?, ?)", (username, hash_password(password)))
        conn.commit()
        conn.close()
        print(f"[DB] User '{username}' registered")
        return True
    
    except sqlite3.IntegrityError:
        print(f"[DB] Registration failed - '{username}' already exists")
        return False
    
    except Exception as e:
        print(f"[DB ERROR] register_user: {e}")
        return False
    
def verify_user(username, password):
    """
    Checks if the username and password entered match what is stored in the database.
    The password is hashed before comparing since we never store plain text passwords.
    Returns True if credentials are correct, False if wrong or user not found.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()

        # Fetch the stored hashed password for this username
        cursor.execute(
            "SELECT password_hash FROM users WHERE username = ?",
            (username,)
        )

        row = cursor.fetchone()
        conn.close()

        # If no row returned the username does not exist
        if row is None:
            return False

        # Hash the entered password and compare it to the stored hash
        return row[0] == hash_password(password)

    except Exception as e:
        print(f"[DB ERROR] verify_user: {e}")
        return False
    
def set_user_status(username, status):
    """
    Updates a user's status to 'online' or 'offline'.
    Called by the server on login and logout.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET status = ? WHERE username = ?", (status, username))
        conn.commit()
        conn.close()
    except Exception as e:
        print(f"[DB ERROR] set_user-status: {e}")

def save_message(sender, receiver, msg_type, content, timestamp):
    """
    Stores a message for a user who is currently offline.
    Delivered is set at 0 until the recipient comes back online 
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.excecute("""INSERT INTO messages (sender, receiver, msg_type, content, timestamp) VALUES (?, ?, ?, ?, ?, 0)""", (sender, receiver, msg_type, content, timestamp))
        conn.commit()
        conn.close()
        print(f"[DB] Message from '{sender}' to '{receiver}' stored.")

    except Exception as e:
        print(f"[DB] save_message: {e}")

