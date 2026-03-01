# Ranwashe Mukovhe
# UDP Relay - forwards status updates between clients
#
# This file runs as a background thread alongside the TCP server.
# It listens on UDP port 9001 for status messages like TYPING,
# USER_ONLINE, USER_OFFLINE and forwards them to the recipient.
#
# The key difference from the TCP server:
#   TCP - one thread per client, connection stays open
#   UDP - one loop handles everyone, no connection at all

import socket
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import (
    HOST, UDP_PORT, BUFFER_SIZE,
    TYPING, USER_ONLINE, USER_OFFLINE, KEEP_ALIVE,
    FIELD_TYPE, FIELD_FROM, FIELD_TO
)
from utils.message import parse_udp_message, build_udp_message

from server.server import online_clients, online_clients_lock

UDP_MESSAGE_TYPES = {TYPING, USER_ONLINE, USER_OFFLINE, KEEP_ALIVE}