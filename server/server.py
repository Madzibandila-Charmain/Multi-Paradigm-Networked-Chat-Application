# Ranwashe Mukovhe - Main TCP server
# This file is the heart of the chat application. It manages all connected clients, routes messages between them,
# handles login and logout, and coordinates with the database.

import socket 
import threading
import sys
import os
import time

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

from database.db_manager import (
    verify_user, set_user_status, save_message,
    get_offline_messages, mark_delivered,
    get_group_members, is_blocked,
    block_user, create_group, add_to_group, remove_from_group
)

online_clients = {}
online_clients_lock = threading.Lock()

def add_online_client(username, client_socket):
    with online_clients_lock:
        online_clients[username] = client_socket

def remove_online_client(username):
    with online_clients_lock:
        if username in online_clients:
            del online_clients[username]

def get_online_client_socket(username):
    with online_clients_lock:
        return online_clients.get(username, None)

def is_online(username):
    with online_clients_lock:
        return username in online_clients

def send_message(sock, msg_type, sender, receiver, body=""):
    """
    Builds TCP message using our protocol format and sends it.
    Returns True if sent successfully, False otherwise.
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
    then add the raw file bytes directly after in one sendall call.
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

def receive_full_message(sock):
    """
    Reads a complete message from a socket one chunk at a time.
    Returns (header_dict, body_bytes) or (None, None) if connection dropped.
    """
    try:
        raw = b""
        separator = HEADER_BODY_SEPARATOR.encode("utf-8")

        while separator not in raw:
            chunk = sock.recv(BUFFER_SIZE)
            if not chunk:
                return None, None
            raw += chunk

        header_bytes, leftover = raw.split(separator, 1)
        header = parse_tcp_header(header_bytes.decode("utf-8"))

        if header is None:
            return None, None

        body_size = int(header.get(FIELD_SIZE, 0))
        body = leftover

        while len(body) < body_size:
            chunk = sock.recv(BUFFER_SIZE)
            if not chunk:
                break
            body += chunk

        return header, body[:body_size]

    except Exception as e:
        print(f"[ERROR] receive_full_message: {e}")
        return None, None

def deliver_offline_messages(username, client_socket):
    """
    Fetches all undelivered messages from the database and sends them
    to the user one by one after login.
    """
    messages = get_offline_messages(username)
    for msg in messages:
        if not messages:
            return
        time.sleep(0.1) # Waits for the login ACK to arrive and to be processed first 
        send_message(client_socket, msg["msg_type"], msg["sender"], username, msg["content"])
        mark_delivered(msg["message_id"])

def handle_login(client_socket, header, body):
    """
    Handles a LOGIN message. Verifies credentials, adds client to
    online_clients, broadcasts status, and delivers offline messages.
    Returns the username on success, None on failure.
    """
    username = header.get(FIELD_FROM)
    password = body.decode("utf-8").replace("password: ", "").strip() if body else ""

    if not username or not password:
        send_message(client_socket, ERROR, "server", "unknown", "Missing username or password")
        return None

    if not verify_user(username, password):
        send_message(client_socket, ERROR, "server", username, "Invalid credentials")
        return None

    print(f"[LOGIN] {username} logged in")
    add_online_client(username, client_socket)
    broadcast_status(username, USER_ONLINE)
    send_message(client_socket, ACK, "server", username, "Login successful")
    deliver_offline_messages(username, client_socket)

    return username

def handle_logout(username):
    """
    Cleans up when a user disconnects. Removes them from online_clients
    and broadcasts offline status to everyone.
    """
    if username:
        remove_online_client(username)
        broadcast_status(username, USER_OFFLINE)
        set_user_status(username, "offline")
        print(f"[LOGOUT] {username} disconnected")

def broadcast_status(username, status_type):
    """
    Sends USER_ONLINE or USER_OFFLINE to everyone currently online
    except the user the update is about.
    """
    with online_clients_lock:
        recipients = {u: s for u, s in online_clients.items() if u != username}

    for recipient, sock in recipients.items():
        try:
            msg = build_tcp_message(status_type, username, recipient, "")
            sock.sendall(msg.encode("utf-8"))
        except Exception as e:
            print(f"[ERROR] Could not send {status_type} to {recipient}: {e}")

def route_message(header, body, sender_socket):
    """
    Routes a message from sender to the recipient.
    Delivers directly if online, stores in database if offline.
    """
    sender   = header.get(FIELD_FROM)
    receiver = header.get(FIELD_TO)
    msg_type = header.get(FIELD_TYPE)

    if not sender or not receiver:
        send_message(sender_socket, ERROR, "server", sender or "unknown", "Missing FROM or TO field")
        return

    if is_blocked(receiver, sender):
        send_message(sender_socket, MESSAGE_FAILED, "server", sender, f"{receiver} has blocked you")
        return

    recipient_socket = get_online_client_socket(receiver)

    if recipient_socket:
        is_file = msg_type in [IMAGE, VIDEO_FILE, AUDIO_FILE, DOCUMENT]

        if is_file:
            success = send_file(recipient_socket, msg_type, sender, receiver, body)
        else:
            body_text = body.decode("utf-8") if body else ""
            success = send_message(recipient_socket, msg_type, sender, receiver, body_text)

        if success:
            send_message(sender_socket, ACK, "server", sender, f"Message delivered to {receiver}")
            print(f"[ROUTE] {msg_type} from {sender} to {receiver} delivered")
        else:
            send_message(sender_socket, MESSAGE_FAILED, "server", sender, f"Could not deliver to {receiver}")
    else:
        body_text = body.decode("utf-8") if body else ""
        save_message(sender, receiver, msg_type, body_text, get_timestamp())
        print(f"[STORE] {receiver} offline. Message from {sender} stored")
        send_message(sender_socket, ACK, "server", sender, f"{receiver} is offline. Message stored.")

def route_group_message(header, body, sender_socket):
    """
    Routes a message to all members of a group.
    Sends to every online member except the sender.
    Stores for offline members.
    """
    sender     = header.get(FIELD_FROM)
    group_name = header.get(FIELD_TO)
    body_text  = body.decode("utf-8") if body else ""

    members = get_group_members(group_name)
    print(f"[DEBUG] Group '{group_name}' members: {members}")  # add this
    print(f"[DEBUG] Online clients: {list(online_clients.keys())}")  # add this

    if not members:
        send_message(sender_socket, ERROR, "server", sender, f"Group '{group_name}' not found or empty")
        return

    delivered = 0
    for member in members:
        if member == sender:
            continue
        # check if member is blocked by sender
        if is_blocked(member, sender):
            continue # skip sliently, dont deliver to this member
        sock = get_online_client_socket(member)
        if sock:
            send_message(sock, TEXT, sender, member, f"[{group_name}] {body_text}")
            delivered += 1
        else:
            save_message(sender, member, TEXT, f"[{group_name}] {body_text}", get_timestamp())

    send_message(sender_socket, ACK, "server", sender, f"Group message sent to {delivered} members")
    print(f"[GROUP] {sender} sent message to group '{group_name}'")

def handle_client(client_socket, client_address):
    """
    The main loop for one connected client.
    Reads messages one at a time and routes each based on its TYPE field.
    The finally block always runs to clean up on exit or crash.
    """
    print(f"[CONNECT] New connection from {client_address}")
    username = None

    try:
        while True:
            header, body = receive_full_message(client_socket)

            if header is None:
                print(f"[DISCONNECT] {username or client_address} lost connection")
                break

            msg_type = header.get(FIELD_TYPE)
            print(f"[RECV] {msg_type} from {header.get(FIELD_FROM, '?')}")

            if msg_type == LOGIN:
                username = handle_login(client_socket, header, body)
                if username is None:
                    break

            elif msg_type == LOGOUT:
                send_message(client_socket, ACK, "server", username, "Logged out")
                break

            elif msg_type in [TEXT, IMAGE, VIDEO_FILE, AUDIO_FILE, DOCUMENT]:
                route_message(header, body, client_socket)

            elif msg_type == "GROUP_MSG":
                route_group_message(header, body, client_socket)

            elif msg_type == BLOCK_USER:
                target = header.get(FIELD_TO)
                block_user(username, target)
                send_message(client_socket, ACK, "server", username, f"{target} has been blocked")
                print(f"[BLOCK] {username} blocked {target}")

            elif msg_type == CREATE_GROUP:
                group_name = body.decode("utf-8").strip() if body else ""
                create_group(group_name, username)
                send_message(client_socket, ACK, "server", username, f"Group '{group_name}' created")
                print(f"[GROUP] {username} created group '{group_name}'")

            elif msg_type == JOIN_GROUP:
                group_name = body.decode("utf-8").strip() if body else ""
                add_to_group(group_name, username)
                send_message(client_socket, ACK, "server", username, f"Joined group '{group_name}'")

            elif msg_type == ADD_USER:
                # body contains "group_name:username_to_add"
                body_text = body.decode("utf-8").strip() if body else ""
                parts = body_text.split(":", 1)
                if len(parts) == 2:
                    group_name  = parts[0].strip()
                    user_to_add = parts[1].strip()
                    add_to_group(group_name, user_to_add)
                    send_message(client_socket, ACK, "server", username, f"{user_to_add} added to '{group_name}'")
                    print(f"[GROUP] {username} added {user_to_add} to '{group_name}'")
                else:
                    send_message(client_socket, ERROR, "server", username, "Invalid ADD_USER format")

            elif msg_type == REMOVE_USER:
                body_text = body.decode("utf-8").strip() if body else ""
                parts = body_text.split(":", 1)
                if len(parts) == 2:
                    group_name     = parts[0].strip()
                    user_to_remove = parts[1].strip()
                    remove_from_group(group_name, user_to_remove)
                    send_message(client_socket, ACK, "server", username, f"{user_to_remove} removed from '{group_name}'")
                else:
                    send_message(client_socket, ERROR, "server", username, "Invalid REMOVE_USER format")

            elif msg_type == EXIT_GROUP:
                group_name = body.decode("utf-8").strip() if body else ""
                remove_from_group(group_name, username)
                send_message(client_socket, ACK, "server", username, f"Left group '{group_name}'")

            else:
                print(f"[WARN] Unknown message type: {msg_type}")
                send_message(client_socket, ERROR, "server", username or "unknown", f"Unknown message type: {msg_type}")

    except Exception as e:
        print(f"[ERROR] handle_client crashed for {username}: {e}")

    finally:
        handle_logout(username)
        client_socket.close()
        print(f"[CLOSED] {username or client_address} connection closed")

def start_server():
    """
    Creates the TCP server socket and starts accepting connections.
    Each new client gets its own thread running handle_client.
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, TCP_PORT))
    server_socket.listen(MAX_CLIENTS)

    print(f"[SERVER] Listening on {HOST}:{TCP_PORT}")
    print(f"[SERVER] Waiting for connections... (Ctrl+C to stop)")

    try:
        while True:
            client_socket, client_address = server_socket.accept()
            thread = threading.Thread(
                target=handle_client,
                args=(client_socket, client_address),
                daemon=True
            )
            thread.start()
            print(f"[SERVER] Active connections: {threading.active_count() - 1}")

    except KeyboardInterrupt:
        print("\n[SERVER] Shutting down")
    finally:
        server_socket.close()


if __name__ == "__main__":
    from server.udp_relay import start_udp_relay

    udp_thread = threading.Thread(target=start_udp_relay, daemon=True)
    udp_thread.start()
    print("[SERVER] UDP relay started on port 9001")

    start_server()