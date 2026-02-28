# Ranwashe Mukovhe
# Main TCP server 

import socket 
import threading
import sys
import os

# Add parent directory to path so we can import constants and utils(messages)
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import (
    HOST, TCP_PORT, BUFFER_SIZE, MAX_CLIENTS,
    LOGIN, LOGOUT, TEXT, IMAGE, VIDEO_FILE, AUDIO_FILE, DOCUMENT,
    ACK, ERROR, USER_ONLINE, USER_OFFLINE, MESSAGE_FAILED,
    CREATE_GROUP, JOIN_GROUP, ADD_USER, REMOVE_USER, EXIT_GROUP, BLOCK_USER,
    FIELD_TYPE, FIELD_FROM, FIELD_TO, FIELD_SIZE,
    HEADER_BODY_SEPARATOR
)
from utils.message import build_tcp_message, parse_tcp_header, build_udp_message, get_timestamp

# Import db_manager
from database.db_manager import (verify_user, set_user_status, save_message, get_offline_messages, mark_delivered, get_group_members, is_blocked)

# Shared states 
# The lock is needed because multiple threads run at the same time
# and they all share this dictionary. Without the lock two threads
# could write to it at the same time and corrupt it.
# This is the same idea as "synchronized" in Java.

online_clients = {}  # This dictionary keeps track of everyone who is currently online.
online_clients_lock = threading.Lock()

def add_online_client(username, client_socket):
    """
    Adds a newly logged-in user to the online clients dictionary.
    The 'with' block acquires the lock, does the work, then releases it.
    Only one thread can be inside a 'with lock' block at a time.
    """
    with online_clients_lock:
        online_clients[username] = client_socket

def remove_online_client(username):
    """
    Removes a user from the online clients dictionary when they disconnect.
    Checks if they exist first to avoid a KeyError crash.
    """
    with online_clients_lock:
        if username in online_clients:
            del online_clients[username]

def get_online_client_socket(username):
    """
    Looks up a users socket by their username
    Returns their socket if online, or None if they are not in the dictionary
    """
    with online_clients_lock:
        return online_clients.get(username, None)
    
def is_online(username):
    """
     Checks if a username is currently in the online clients dictionary.
    """
    with online_clients_lock:
        return username in online_clients