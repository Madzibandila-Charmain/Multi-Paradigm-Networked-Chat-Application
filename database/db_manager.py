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

def get_offline_messages(username):
    """
    Retrieves all underlivered messages for that user.
    Called whne  a user logs in so that they receive messages sent while offline
    Returns a lsit of dicts ordered from oldest to newest.
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""SELECT message_id, sender, msg_type, content, timestamp FROM messages WHERE receiver = ? AND delivered = 0 ORDER BY timestamp ASC""", (username))

        rows = cursor.fetchall()
        conn.close()

        return [{"message_id": r[0], "sender": r[1], "msg_type": r[2], "content": r[3], "timestamp": r[4]} for r in rows]
    
    except Exception as e:
        print(f"[DB ERROR] get_offline_messages: {e}")
        return []
    
def mark_delivered(message_id):
    """
    Mark a message as delivered after it has been sent to the recipient.
    Sets delivered = 1 so its not sent again on the next log
    """
    try:
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("UPDATE message SET delivered = 1 WHERE message_id = ?", (message_id))
        conn.commit()
        conn.close()

    except Exception as e:
        print(f"[DB ERROR] mark_delivered: {e}")