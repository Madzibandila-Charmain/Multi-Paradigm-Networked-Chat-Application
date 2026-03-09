# CSC3002F - Multi-Paradigm Chat Application
# Shared constants - import this file in all modules

import socket

def get_local_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("8.8.8.8", 80))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()

# Ports
TCP_PORT = 9000
UDP_PORT = 9001

# Server
HOST = get_local_ip()
BUFFER_SIZE = 4096
MAX_CLIENTS = 10

# Database
DB_NAME = "ChatApp.db"

# Media
MEDIA_DIR = "received_files"

# Command messages (TCP)
REGISTER     = "REGISTER"
LOGIN        = "LOGIN"
LOGOUT       = "LOGOUT"
CREATE_GROUP = "CREATE_GROUP"
JOIN_GROUP   = "JOIN_GROUP"
ADD_USER     = "ADD_USER"
REMOVE_USER  = "REMOVE_USER"
EXIT_GROUP   = "EXIT_GROUP"
BLOCK_USER   = "BLOCK_USER"

# P2P messages (TCP signalling)
P2P_REGISTER = "P2P_REGISTER"   # Client → Server: register p2p listen port after login
P2P_REQUEST  = "P2P_REQUEST"    # Client → Server: request direct transfer to peer
P2P_SIGNAL   = "P2P_SIGNAL"     # Server → Sender: peer's IP:port, connect and send
P2P_INCOMING = "P2P_INCOMING"   # Server → Receiver: expect incoming direct connection
P2P_DENIED   = "P2P_DENIED"     # Server → Client: peer offline, fall back to server routing

# Control messages
ACK            = "ACK"
ERROR          = "ERROR"
MESSAGE_FAILED = "MESSAGE_FAILED"
TYPING         = "TYPING"
USER_ONLINE    = "USER_ONLINE"
USER_OFFLINE   = "USER_OFFLINE"
KEEP_ALIVE     = "KEEP_ALIVE"

# Data messages (TCP)
TEXT       = "TEXT"
IMAGE      = "IMAGE"
VIDEO_FILE = "VIDEO_FILE"
AUDIO_FILE = "AUDIO_FILE"
DOCUMENT   = "DOCUMENT"

# Header fields
FIELD_TYPE      = "TYPE"
FIELD_FROM      = "FROM"
FIELD_TO        = "TO"
FIELD_TIMESTAMP = "TIMESTAMP"
FIELD_SIZE      = "SIZE"

# Message separators
HEADER_BODY_SEPARATOR  = "\r\n\r\n"
HEADER_FIELD_SEPARATOR = "\r\n"