# Ranwashe Mukovhe
# UDP Relay - forwards real-time status updates between clients.
#
# Listens on UDP port 9001 for TYPING and KEEP_ALIVE packets.
# TYPING is forwarded to the recipient over their TCP connection.
# KEEP_ALIVE is dropped intentionally - it is a client-to-server heartbeat
# and should never be forwarded to another client.
#
# Note on forwarding over TCP: the relay receives TYPING over UDP but delivers
# it via the recipient's TCP socket. This is because clients do not register a
# UDP receive port, so the relay has no address to send a datagram back to.
# Forwarding over TCP is functionally equivalent for TYPING indicators.

import socket
import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import (
    HOST, UDP_PORT, BUFFER_SIZE,
    TYPING, KEEP_ALIVE,
    FIELD_TYPE, FIELD_FROM, FIELD_TO
)
from utils.message import parse_udp_message, build_tcp_message

# Shared client registry from the TCP server
from server.server import online_clients, online_clients_lock
# Only these message types are allowed through the relay
# Using a set instead of a list because checking membership is faster
# KEEP_ALIVE is excluded - it's for server monitoring, not client-to-client forwarding
RELAY_TYPES = {TYPING}

def forward_typing(msg_type, sender, receiver):
    """
    Looks up the recipient in online_clients and forwards the status message.
    If the recipient is offline the message is dropped - UDP never stores
    messages for later delivery, it is fire and forget.
    """
    with online_clients_lock:
        recipient_socket = online_clients.get(receiver, None)

    if recipient_socket is None:
        print(f"[UDP RELAY] {receiver} offline - {msg_type} from {sender} dropped")
        return

    try:
        message = build_tcp_message(msg_type, sender, receiver, "")
        recipient_socket.sendall(message.encode("utf-8"))
        print(f"[UDP RELAY] {msg_type} from {sender} forwarded to {receiver}")
    except Exception as e:
        print(f"[UDP RELAY ERROR] Could not forward to {receiver}: {e}")

def start_udp_relay():
    """
    Creates a UDP socket, binds to port 9001 and loops waiting for messages.

    The key difference from the TCP server:
    TCP uses accept() and spawns a thread per client because each client
    has a persistent connection. UDP has no connection at all - every packet
    arrives independently with the sender's address attached. One loop
    handles messages from every client so no threads are needed.

    recvfrom() is the UDP equivalent of recv() - it returns the data AND
    the sender's address (ip, port) because there is no connection to
    tell us who sent it.
    """
    udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    udp_socket.bind((HOST, UDP_PORT))

    print(f"[UDP RELAY] Listening on {HOST}:{UDP_PORT}")

    while True:
        try:
            data, sender_address = udp_socket.recvfrom(BUFFER_SIZE)
            raw_message = data.decode("utf-8")
            parsed = parse_udp_message(raw_message)

            if parsed is None:
                print(f"[UDP RELAY] Malformed message from {sender_address}, dropped")
                continue

            msg_type = parsed.get(FIELD_TYPE)
            sender   = parsed.get(FIELD_FROM)
            receiver = parsed.get(FIELD_TO)

            if not msg_type or not sender or not receiver:
                print(f"[UDP RELAY] Incomplete message from {sender_address}, dropped")
                continue

            if msg_type == KEEP_ALIVE:
                # Expected - client heartbeat to keep NAT maaping alive.
                print(f"[UDP RELAY] KEEP_ALIVE from {sender} (dropped as expected)")
                continue

            if msg_type in RELAY_TYPES:
                print(f"[UDP RELAY] Received {msg_type} from {sender} for {receiver}")
                forward_typing(msg_type, sender, receiver)
            else:
                print(f"[UDP RELAY] Unexpected message type {msg_type}, dropped")

        except Exception as e:
            # Print the error and keep going - never let one bad message stop the relay
            print(f"[UDP RELAY ERROR] {e}")
            continue


if __name__ == "__main__":
    start_udp_relay()