# A program which implements the client side of a Multi-Paradigm Chat Application
# Author: MADZIBANDILA CHARMAIN
# Date: 28 February 2026

import socket
import threading
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import (
    HOST, TCP_PORT, UDP_PORT, BUFFER_SIZE, MEDIA_DIR,
    LOGIN, LOGOUT, TEXT, IMAGE, VIDEO_FILE, AUDIO_FILE, DOCUMENT,
    ACK, ERROR, MESSAGE_FAILED, TYPING, USER_ONLINE, USER_OFFLINE,
    KEEP_ALIVE, BLOCK_USER, CREATE_GROUP, JOIN_GROUP, ADD_USER,
    REMOVE_USER, EXIT_GROUP,
    FIELD_TYPE, FIELD_FROM, FIELD_TO, FIELD_SIZE,
    HEADER_BODY_SEPARATOR
)
from utils.message import (
    build_tcp_message, parse_tcp_header,
    build_udp_message, parse_udp_message, get_timestamp
)

class ClientHandler:

    def __init__(self):
        self.username = None
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.udp_socket = socket.socket(socket.AF_NET, socket.SOCK_DGRAM)