# Ranwashe Mukovhe - Database manager creation
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
    Opens and returns a connection to the database.
    check_same_thread=False is required because multiple server threads will
    call these functions at the same time.

    WAL mode is set once here. It allows concurrent readers alongside a single
    writer, which eliminates most locking under normal server load.
    Busy timeout of 5000 ms means SQLite will retry for up to 5 seconds before
    raising OperationalError instead of failing instantly.
    """
    conn = sqlite3.connect(DB_NAME, check_same_thread=False, timeout=5)
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA busy_timeout=5000")  # retry for 5 s instead of failing instantly
    return conn

def hash_password(password):
    """
    Hash the password before storing it so plain text passwords are never in
    the database.
    """
    return hashlib.sha256(password.encode("utf-8")).hexdigest()

def register_user(username, password):
    """
    Register a new user account with a hashed password.
    Returns True if registration is successful, False if the username already exists.
    """
    conn = get_connection()
    try:
        with conn:  # auto-commits on success, auto-rolls back on exception
            conn.execute(
                "INSERT INTO users (username, password_hash) VALUES (?, ?)",
                (username, hash_password(password))
            )
        print(f"[DB] User '{username}' registered")
        return True

    except sqlite3.IntegrityError:
        print(f"[DB] Registration failed - '{username}' already exists")
        return False

    except Exception as e:
        print(f"[DB ERROR] register_user: {e}")
        return False

    finally:
        conn.close()  # always runs — no more leaked connections

def verify_user(username, password):
    """
    Checks if the username and password match what is stored in the database.
    Returns True if credentials are correct, False if wrong or user not found.
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT password_hash FROM users WHERE username = ?", (username,)
        )
        row = cursor.fetchone()
        if row is None:
            return False
        return row[0] == hash_password(password)

    except Exception as e:
        print(f"[DB ERROR] verify_user: {e}")
        return False

    finally:
        conn.close()

def set_user_status(username, status):
    """
    Updates a user's status to 'online' or 'offline'.
    Called by the server on login and logout.
    """
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE users SET status = ? WHERE username = ?", (status, username)
            )
    except Exception as e:
        print(f"[DB ERROR] set_user_status: {e}")
    finally:
        conn.close()

def get_group_creator(group_name):
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT created_by FROM groups WHERE group_name = ?", (group_name,)
        )
        row = cursor.fetchone()
        return row[0] if row else None
    except Exception as e:
        print(f"[DB ERROR] get_group_creator: {e}")
        return None
    finally:
        conn.close()

def user_exists(username):
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT 1 FROM users WHERE username = ?", (username,)
        )
        return cursor.fetchone() is not None
    except Exception as e:
        print(f"[DB ERROR] user_exists: {e}")
        return False
    finally:
        conn.close()

def save_message(sender, receiver, msg_type, content, timestamp):
    """
    Stores a message for a user who is currently offline.
    delivered is set to 0 until the recipient comes back online.
    """
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                """INSERT INTO messages
                   (sender, receiver, msg_type, content, timestamp, delivered)
                   VALUES (?, ?, ?, ?, ?, 0)""",
                (sender, receiver, msg_type, content, timestamp)
            )
        print(f"[DB] Message from '{sender}' to '{receiver}' stored.")
    except Exception as e:
        print(f"[DB ERROR] save_message: {e}")
    finally:
        conn.close()

def get_offline_messages(username):
    """
    Retrieves all undelivered messages for a user.
    Called when a user logs in so they receive messages sent while offline.
    Returns a list of dicts ordered oldest to newest.
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            """SELECT message_id, sender, msg_type, content, timestamp
               FROM messages
               WHERE receiver = ? AND delivered = 0
               ORDER BY timestamp ASC""",
            (username,)
        )
        rows = cursor.fetchall()
        return [
            {"message_id": r[0], "sender": r[1], "msg_type": r[2],
             "content": r[3], "timestamp": r[4]}
            for r in rows
        ]
    except Exception as e:
        print(f"[DB ERROR] get_offline_messages: {e}")
        return []
    finally:
        conn.close()

def mark_delivered(message_id):
    """
    Mark a message as delivered after it has been sent to the recipient.
    Sets delivered = 1 so it is not sent again on the next login.
    """
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "UPDATE messages SET delivered = 1 WHERE message_id = ?", (message_id,)
            )
    except Exception as e:
        print(f"[DB ERROR] mark_delivered: {e}")
    finally:
        conn.close()

def create_group(group_name, creator_username):
    """
    Creates a new group and adds the creator as the first member.
    Returns True if successful, False if the group name already exists.
    Both inserts happen in a single transaction so they either both succeed
    or both roll back.
    """
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "INSERT INTO groups (group_name, created_by) VALUES (?, ?)",
                (group_name, creator_username)
            )
            conn.execute(
                "INSERT INTO group_members (group_name, username) VALUES (?, ?)",
                (group_name, creator_username)
            )
        print(f"[DB] Group '{group_name}' created by '{creator_username}'")
        return True

    except sqlite3.IntegrityError:
        print(f"[DB] Group '{group_name}' already exists")
        return False

    except Exception as e:
        print(f"[DB ERROR] create_group: {e}")
        return False

    finally:
        conn.close()

def group_exists(group_name):
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT 1 FROM groups WHERE group_name = ?", (group_name,)
        )
        return cursor.fetchone() is not None
    except Exception as e:
        print(f"[DB ERROR] group_exists: {e}")
        return False
    finally:
        conn.close()

def add_to_group(group_name, username):
    """
    Adds a user to an existing group.
    Returns True if successful, False if the user is already a member.
    """
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "INSERT INTO group_members (group_name, username) VALUES (?, ?)",
                (group_name, username)
            )
        print(f"[DB] '{username}' added to group '{group_name}'")
        return True

    except sqlite3.IntegrityError:
        print(f"[DB] '{username}' is already in group '{group_name}'")
        return False

    except Exception as e:
        print(f"[DB ERROR] add_to_group: {e}")
        return False

    finally:
        conn.close()

def remove_from_group(group_name, username):
    """Removes a user from a group."""
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "DELETE FROM group_members WHERE group_name = ? AND username = ?",
                (group_name, username)
            )
        print(f"[DB] '{username}' removed from group '{group_name}'")
    except Exception as e:
        print(f"[DB ERROR] remove_from_group: {e}")
    finally:
        conn.close()

def get_group_members(group_name):
    """
    Returns a list of usernames who are members of the given group.
    Returns an empty list if the group does not exist.
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT username FROM group_members WHERE group_name = ?", (group_name,)
        )
        return [row[0] for row in cursor.fetchall()]
    except Exception as e:
        print(f"[DB ERROR] get_group_members: {e}")
        return []
    finally:
        conn.close()

def block_user(username, blocked_username):
    """
    Blocks a user so they cannot send messages to username.
    INSERT OR IGNORE prevents errors if the same user is blocked twice.
    Returns True if successful.
    """
    conn = get_connection()
    try:
        with conn:
            conn.execute(
                "INSERT OR IGNORE INTO blocked_users (user_id, blocked_user_id) VALUES (?, ?)",
                (username, blocked_username)
            )
        print(f"[DB] '{username}' blocked '{blocked_username}'")
        return True
    except Exception as e:
        print(f"[DB ERROR] block_user: {e}")
        return False
    finally:
        conn.close()

def is_blocked(username, sender_username):
    """
    Checks if sender_username is blocked by username.
    The server calls this before routing every message.
    Returns True if blocked, False if not.
    """
    conn = get_connection()
    try:
        cursor = conn.execute(
            "SELECT 1 FROM blocked_users WHERE user_id = ? AND blocked_user_id = ?",
            (username, sender_username)
        )
        return cursor.fetchone() is not None
    except Exception as e:
        print(f"[DB ERROR] is_blocked: {e}")
        return False
    finally:
        conn.close()