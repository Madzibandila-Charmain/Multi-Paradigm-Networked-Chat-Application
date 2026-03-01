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
# The lock is needed because multiple threads run at the same time and they all share this dictionary. Without the lock two threads
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
    
# Helper functions 
# These functions handle sending data through sockets. Sockets only understand bytes so the string must be encoded 

def send_message(sock, msg_type, sender, receiver, body=""):
    """
    Builds TCP message using our protocol format and sends it
    Return True if sent successfully, False otherwise
    """
    try:
        message = build_tcp_message(msg_type, sender, receiver, body)
        sock.sendall(message.encode("utf-8"))
        return True
    
    except Exception as e:
        print(f"[ERROR] Failed to send {msg_type} to {receiver}: {e}")
        return False
    
def send_file(sock, msg_type, sender, receiver, file_data):
    """
    Sends a binary file over TCP.
    Files are raw bytes so we build the header as text, encode it,
    then add the raw file bytes directly after - all in one sendall call.
    The receiver knows how many bytes to read from the SIZE field.
    """
    try:
        size = len(file_data)
        header = (
            f"TYPE: {msg_type}\r\n"
            f"FROM: {sender}\r\n"
            f"TO: {receiver}\r\n"
            f"TIMESTAMP: {get_timestamp()}\r\n"
            f"SIZE: {size}"
            f"{HEADER_BODY_SEPARATOR}"
        )
        sock.sendall(header.encode("utf-8") + file_data)
        return True
    
    except Exception as e:
        print(f"[ERROR] Failed to send file to {receiver}: {e}")
        return False
    
# Receive helper  function
def receive_full_message(sock):
    """
    Reads a complete message from a socket one chunck at a time
    Keeps reading until the full header and body have arrived
    Returns (header_dict, boudy_bytes) or (None, None) if connection dropped.
    """
    try:
        raw = b""  # b"" means empt bytes
        separator = HEADER_BODY_SEPARATOR.encode("utf-8")

        # Keep reading chunkcs until we have the complete header
        while separator not in raw:
            chunk = sock.recv(BUFFER_SIZE)
            if not chunk:
                # Empty chunk means client disconnected
                return None, None
            raw += chunk

        # Split at the separator- header on the left and start of body on the right
        header_bytes, leftover =  raw.split(separator, 1)
        header = parse_tcp_header(header_bytes.decode("uft-8"))

        if header is None:
            return None, None
        
        # Read the body base on the size field in the header
        body_size = int(header.get(FIELD_SIZE, 0))
        body = leftover

        # Keep reading until we have all the body bytes
        while len(body) < body_size:
            chunk = sock.recv(BUFFER_SIZE)
            if not chunk:
                break
            body += chunk

        return header, body[:body_size]

    except Exception as e:
        print(f"[ERROR] receive_full_message: {e}")
        return None, None