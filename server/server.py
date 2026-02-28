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
