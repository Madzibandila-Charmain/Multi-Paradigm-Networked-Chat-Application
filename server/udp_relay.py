# Ranwashe Mukovhe
# UDP Relay - forwards status updates between clients
#
# Runs as a background thread alongside the TCP server.
# Listens on UDP port 9001 for TYPING, USER_ONLINE, USER_OFFLINE
# and forwards them immediately to the recipient.
# Unlike TCP there is no connection, no ACK, no storage - fire and forget.

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

# Import the shared online_clients dictionary from server.py
# so we know each client's socket and can forward messages to them
from server.server import online_clients, online_clients_lock

# Only these message types are allowed through the relay
# Using a set instead of a list because checking membership is faster
UDP_MESSAGE_TYPES = {TYPING, USER_ONLINE, USER_OFFLINE, KEEP_ALIVE}


def forward_status(udp_socket, msg_type, sender, receiver):
    """
    Looks up the recipient in online_clients and forwards the status message.
    If the recipient is offline the message is dropped - UDP never stores
    messages for later delivery, it is fire and forget.
    """
    import threading

    with online_clients_lock:
        recipient_socket = online_clients.get(receiver, None)

    if recipient_socket is None:
        print(f"[UDP RELAY] {receiver} offline, {msg_type} from {sender} dropped")
        return

    try:
        message = build_udp_message(msg_type, sender, receiver)
        recipient_socket.sendall(message.encode("utf-8"))
        print(f"[UDP RELAY] {msg_type} from {sender} forwarded to {receiver}")
    except Exception as e:
        print(f"[UDP RELAY ERROR] Could not forward to {receiver}: {e}")

