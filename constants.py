# CSC3002F - Multi-Paradigm Chat Application
# Shared constants - import this file in all modules

# Ports
TCP_PORT = 9000
UDP_PORT = 9001

# Server
HOST = "196.24.141.106"
BUFFER_SIZE = 4096
MAX_CLIENTS = 10

# Database
DB_NAME = "ChatApp.db"

# Media
MEDIA_DIR = "received_files"

# Command messages (TCP)
LOGIN        = "LOGIN"
LOGOUT       = "LOGOUT"
CREATE_GROUP = "CREATE_GROUP"
JOIN_GROUP   = "JOIN_GROUP"
ADD_USER     = "ADD_USER"
REMOVE_USER  = "REMOVE_USER"
EXIT_GROUP   = "EXIT_GROUP"
BLOCK_USER   = "BLOCK_USER"

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