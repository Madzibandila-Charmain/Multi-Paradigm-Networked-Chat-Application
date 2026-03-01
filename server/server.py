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
    
def handle_login(client_socket, header, body):
    """
    Handles a LOGIN message from a client.
    Extracts the username from the header and password from the body.
    Adds the client to online_clients if login is successful.
    Returns the username on success, None on failure.
    """
    username = header.get(FIELD_FROM)
    password = body.decode("utf-8").replace("password: ", "").strip() if body else ""

    if not username or not password:
        send_message(client_socket, ERROR, "server", "unknown", "Missing username or password")
        return None
    
    # Verify that the user is in the database
    if not verify_user(username, password):
        send_message(client_socket, ERROR, "server", "username", "Invalid credentials")
        return None
    
    # Successful
    print(f"[LOGIN] {username} logged in")

    # Add to online dictionary so other client can reach them
    add_online_client(username, client_socket)

    # Notify all that the user is online
    broadcast_status(username, USER_ONLINE)

    # Send confimation back to the client
    send_message(client_socket, ACK, "server", username, "Login successful")

    # Deilver offline messages
    deliver_offline_messages(username, client_socket)

    return username

def handle_logout(username):
    """
    Cleans up when a user disconnects - whether they typed quit or their connection just dropped.
    Removes them from online_clients and tells everyone they left.
    """
    if username:
        remove_online_client(username)
        broadcast_status(username, USER_OFFLINE)
        set_user_status(username, "offline")
        print(f"[LOGOUT] {username} disconnected")

def broadcast_status(username, status_type):
    """
    Sends a USER_ONLINE or USER_OFFLINE notification to everyone
    currently online except the user the update is about.

    The dict comprehension on the first line creates a copy of
    online_clients without the user themselves:
    {u: s for u, s in online_clients.items() if u != username}
    means: for every user and socket in the dict, include them
    only if they are not the user we are broadcasting about.
    """
    with online_clients_lock:
        recipients = {u: s for u, s in online_clients.items() if u != username}

    for recipient, sock in recipients.items():
        try:
            msg = build_udp_message(status_type, username, recipient)
            sock.sendall(msg.encode("utf-8"))
        except Exception as e:
            print(f"[ERROR] Could not send {status_type} to {recipient}: {e}")

def route_message(header, body, sender_socket):
    """
    Routes a message from sender to the receiver.
    Looks up the recipient in online_clients.
    If found, sends directly, if not stores ater for delivery.
    """
    sender = header.get(FIELD_FROM)
    receiver = header.get(FIELD_TO)
    msg_type = header.get(FIELD_TYPE)

    if not sender or not receiver:
        send_message(sender_socket, ERROR, "server", sender or "unknown", "Missing FROM or TO field")
        return 
    
    # Checking if user is blocked
    if is_blocked(receiver, sender):
        send_message(sender_socket, MESSAGE_FAILED, "server", sender, f"{receiver} has blocked you")
        return
    
    # Look up the recipient socktet
    recipient_socket = get_online_client_socket(receiver)

    if recipient_socket:
        # Recipient is online - deliver directly to their socket
        is_file = msg_type in [IMAGE, VIDEO_FILE, AUDIO_FILE, DOCUMENT]

        if is_file:
            success = send_file(recipient_socket, msg_type, sender, receiver, body)
        else:
            body_text = body.decode("utf-8") if body else ""
            success = send_file(recipient_socket, msg_type, sender, receiver, body)

        if success:
            send_message(sender, ACK, "server", sender, f"Message delivered to {receiver}")
            print(f"[ROUTE] {msg_type} from {sender} to {receiver} delivered")
        else:
            send_message(sender_socket, MESSAGE_FAILED, "server", sender, f"Could not deliver to {receiver}")
    else:
        # Recipient is offline - store message for when they log in
        save_message(sender, receiver, msg_type, body, get_timestamp())
        print(f"[STORE] {receiver} offline. Message from {sender} stored")
        send_message(sender_socket, ACK, "server", sender, f"{receiver} is offline. Message staored.")

# P2P Signalling. When both the sender and receiver are online and a file transfer is needed
# The server shares both IP addresses so they can connect directly to each other
# After this thr server steps out entirely
def signal_p2p(sender, receiver, sender_socket, receiver_socket):
    """
    Gets both clients' IP addresses and sends each one the other's IP.
    .getpeername() returns the (ip, port) of the connected client.[0] gets just the IP part.
    After this the two clients handle the file transfer themselves.
    """
    try:
        sender_ip   = sender_socket.getpeername()[0]
        receiver_ip = receiver_socket.getpeername()[0]

        send_message(sender_socket, "P2P_SIGNAL", "server", sender, f"peer_ip: {receiver_ip}\npeer_username: {receiver}")

        send_message(receiver_socket, "P2P_SIGNAL", "server", receiver, f"peer_ip: {sender_ip}\npeer_username: {sender}")

        print(f"[P2P] Signalled {sender} and {receiver} for direct transfer")

    except Exception as e:
        print(f"[ERROR] P2P signalling failed: {e}")

# Client Handler 
def handle_client(client_socket, client_address):
    """
    The main loop for one connected client.
    Reads messages one at a time and handles each based on its TYPE field.
    The finally block runs no matter how the loop ends - clean disconnect
    or unexpected crash - so cleanup always happens.
    """
    print(f"[CONNECT] New connection from {client_address}")
    username = None
    
    try:
        while True:
            header, body = receive_full_message(client_socket)

            # None means the connection dropped
            if header is None:
                print(f"[DISCONNECT] {username or client_address} lost connection")
                break

            msg_type = header.get(FIELD_TYPE)
            print(f"[RECV] {msg_type} from {header.get(FIELD_FROM, '?')}")

            if msg_type == LOGIN:
                username = handle_login(client_socket, header, body)
                if username is None:
                    break  # Login failed - close connection

            elif msg_type == LOGOUT:
                send_message(client_socket, ACK, "server", username, "Logged out")
                break  # Clean exit

            elif msg_type in [TEXT, IMAGE, VIDEO_FILE, AUDIO_FILE, DOCUMENT]:
                receiver = header.get(FIELD_TO)
                if msg_type != TEXT and is_online(receiver):
                    # File transfer and recipient is online - use P2P
                    receiver_socket = get_online_client_socket(receiver)
                    signal_p2p(username, receiver, client_socket, receiver_socket)
                else:
                    # Text message or recipient offline - route through server
                    route_message(header, body, client_socket)

            elif msg_type == BLOCK_USER:
                target = header.get(FIELD_TO)
                block_user(username, target)
                send_message(client_socket, ACK, "server", username, f"{target} has been blocked")
                print(f"[BLOCK] {username} blocked {target}")

            elif msg_type == CREATE_GROUP:
                group_name = body.decode("utf-8").strip() if body else ""
                create_group(group_name, username)
                send_message(client_socket, ACK, "server", username, f"Group {group_name} created")
                print(f"[GROUP] {username} created group '{group_name}'")

            elif msg_type == JOIN_GROUP:
                group_name = body.decode("utf-8").strip() if body else ""
                add_to_group(group_name, username)
                send_message(client_socket, ACK, "server", username, f"Joined group {group_name}")

            elif msg_type == ADD_USER:
                send_message(client_socket, ACK, "server", username, "User added")

            elif msg_type == REMOVE_USER:
                send_message(client_socket, ACK, "server", username, "User removed")

            elif msg_type == EXIT_GROUP:
                group_name = body.decode("utf-8").strip() if body else ""
                remove_from_group(group_name, username)
                send_message(client_socket, ACK, "server", username, f"Left group {group_name}")

            else:
                print(f"[WARN] Unknown message type: {msg_type}")
                send_message(client_socket, ERROR, "server", username or "unknown", f"Unknown message type: {msg_type}")

    except Exception as e:
        print(f"[ERROR] handle_client crashed for {username}: {e}")

    finally:
        # This always runs whether we exited cleanly or crashed
        handle_logout(username)
        client_socket.close()
        print(f"[CLOSED] {username or client_address} connection closed")

def start_server():
    """
    Creates the TCP server socket and starts accepting connections.
    AF_INET = IPv4 addresses, SOCK_STREAM = TCP protocol.
    SO_REUSEADDR lets us restart the server quickly without the OS
    blocking the port for a few minutes after shutdown.
    """
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, TCP_PORT))
    server_socket.listen(MAX_CLIENTS)

    print(f"[SERVER] Listening on {HOST}:{TCP_PORT}")
    print(f"[SERVER] Waiting for connections... (Ctrl+C to stop)")

    try:
        while True:
            # accept() blocks here until someone connects
            # Returns a new socket just for that client + their address
            client_socket, client_address = server_socket.accept()

            # Spawn a new thread for this client
            # target = the function to run in the thread
            # args   = the arguments to pass to that function
            # daemon = True means this thread dies when the server stops
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

    # Start UDP relay in background thread alongside TCP server
    udp_thread = threading.Thread(target=start_udp_relay, daemon=True)
    udp_thread.start()
    print("[SERVER] UDP relay started on port 9001")

    start_server()