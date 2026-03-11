# Ranwashe Mukovhe - Main TCP server
# Konke Vezi - aesthetics/ terminal user interface
# This file is the heart of the chat application. It manages all connected clients, routes messages between them,
# handles login and logout, and coordinates with the database.

import socket
import threading
import sys
import os
import time
from datetime import datetime

# Add Colorama imports
from colorama import init, Fore, Back, Style

init()  # Initialize colorama (automatically resets on Windows)

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import *
from utils.message import *
from database.db_manager import *

online_clients = {}
online_clients_lock = threading.Lock()

# Maps username -> (ip, p2p_port) registered after login
p2p_info = {}
p2p_info_lock = threading.Lock()


def add_online_client(username, sock):
    """Add a successfully logged-in client to the online registry."""
    with online_clients_lock:
        online_clients[username] = sock
    print(f"{Fore.GREEN}✓ {Fore.CYAN}{username}{Fore.GREEN} added to online clients{Style.RESET_ALL}")


def remove_online_client(username):
    """Remove a client on logout or disconnect. Safe to call if never registered."""
    with online_clients_lock:
        online_clients.pop(username, None)


def get_online_client_socket(username):
    with online_clients_lock:
        return online_clients.get(username, None)


def is_online(username):
    """
    Return True if the user has an active connection.
    Checks the live dict rather than the DB - the DB status can lag if a
    client drops without sending LOGOUT.
    """
    with online_clients_lock:
        return username in online_clients


# p2p_info helpers
def register_p2p(username, ip, port):
    """
    Store the IP and P2P listen port for a client after login.
    IP is taken from the TCP connection, not the message body, to prevent
    a client from registering a spoofed address.
    """
    with p2p_info_lock:
        p2p_info[username] = (ip, port)
    print(f"{Fore.MAGENTA}P2P registered: {Fore.CYAN}{username}{Fore.MAGENTA} at {ip}:{port}{Style.RESET_ALL}")


def remove_p2p(username):
    """Remove P2P registration on logout. After this, P2P requests to this user get P2P_DENIED."""
    with p2p_info_lock:
        p2p_info.pop(username, None)


def get_p2p_info(username):
    """Return (ip, port) for a user's P2P listen socket, or None if not registered."""
    with p2p_info_lock:
        return p2p_info.get(username)


def send_message(sock, msg_type, sender, receiver, body=""):
    """
    Builds TCP message using our protocol format and sends it.
    Returns True if sent successfully, False otherwise.
    """
    try:
        sock.sendall((build_tcp_message(msg_type, sender, receiver, body)).encode("utf-8"))
        return True
    except Exception as e:
        print(f"{Fore.RED}✗ Failed to send {msg_type} to {receiver}: {e}{Style.RESET_ALL}")
        return False


def send_file(sock, msg_type, sender, receiver, filename, file_data):
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
            f"FILENAME: {filename}\r\n"
            f"SIZE: {size}"
            f"{HEADER_BODY_SEPARATOR}"
        )
        sock.sendall(header.encode("utf-8") + file_data)
        return True
    except Exception as e:
        print(f"{Fore.RED}✗ Failed to send file to {receiver}: {e}{Style.RESET_ALL}")
        return False


def receive_full_message(sock, buf):
    """
    Reads a complete message from a socket one chunk at a time.
    Returns (header_dict, body_bytes, buf) or (None, None, buf) if connection dropped.
    """
    sep = HEADER_BODY_SEPARATOR.encode("utf-8")

    while True:
        if sep in buf:
            break
        try:
            chunk = sock.recv(BUFFER_SIZE)
        except Exception:
            return None, None, buf
        if not chunk:
            return None, None, buf
        buf += chunk

    header_bytes, rest = buf.split(sep, 1)
    header = parse_tcp_header(header_bytes.decode("utf-8"))
    if header is None:
        return None, None, bytearray()

    body_size = int(header.get(FIELD_SIZE, 0))

    while len(rest) < body_size:
        try:
            chunk = sock.recv(BUFFER_SIZE)
        except Exception:
            return None, None, buf
        if not chunk:
            break
        rest += chunk

    body = bytes(rest[:body_size])
    new_buf = bytearray(rest[body_size:])  # leftover belongs to the next message
    return header, body, new_buf


def deliver_offline_messages(username, client_socket):
    """
    Fetches all undelivered messages from the database and sends them
    to the user one by one after login.
    """
    messages = get_offline_messages(username)
    if not messages:
        return
    time.sleep(0.2)

    count = 0
    for msg in messages:
        send_message(client_socket, msg["msg_type"], msg["sender"], username, msg["content"])
        mark_delivered(msg["message_id"])
        count += 1
    print(f"{Fore.YELLOW}[OFFLINE] Delivered {count} stored messages to {username}{Style.RESET_ALL}")


def handle_login(client_socket, client_address, header, body):
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

    print(f"{Fore.GREEN}[LOGIN] {Fore.CYAN}{username}{Fore.GREEN} logged in from {client_address}{Style.RESET_ALL}")
    add_online_client(username, client_socket)
    set_user_status(username, "online")
    broadcast_status(username, USER_ONLINE)
    send_message(client_socket, ACK, "server", username, "Login successful")
    t = threading.Thread(target=deliver_offline_messages, args=(username, client_socket), daemon=True)
    t.start()

    return username


def handle_logout(username):
    """
    Cleans up when a user disconnects. Removes them from online_clients
    and broadcasts offline status to everyone.
    """
    if not username:
        return
    remove_online_client(username)
    remove_p2p(username)
    broadcast_status(username, USER_OFFLINE)
    set_user_status(username, "offline")
    print(f"{Fore.YELLOW}[LOGOUT] {Fore.CYAN}{username}{Fore.YELLOW} disconnected{Style.RESET_ALL}")


def broadcast_status(username, status_type):
    """
    Sends USER_ONLINE or USER_OFFLINE to everyone currently online
    except the user the update is about.
    """
    with online_clients_lock:
        recipients = {u: s for u, s in online_clients.items() if u != username}

    for recipient, sock in recipients.items():
        try:
            sock.sendall(build_tcp_message(status_type, username, recipient, "").encode("utf-8"))
        except Exception as e:
            print(f"{Fore.RED}[ERROR] Could not send {status_type} to {recipient}: {e}{Style.RESET_ALL}")


def route_message(header, body, sender_socket):
    """
    Routes a message from sender to the recipient.
    Delivers directly if online, stores in database if offline.
    Binary files (images, video, audio, documents) are never stored -
    SQLite cannot hold raw binary data. The client blocks this at P2P_DENIED
    but we guard here too in case a file reaches this path unexpectedly.
    """
    sender = header.get(FIELD_FROM)
    receiver = header.get(FIELD_TO)
    msg_type = header.get(FIELD_TYPE)

    if not sender or not receiver:
        send_message(sender_socket, ERROR, "server", sender or "unknown", "Missing FROM or TO field")
        return

    if is_blocked(receiver, sender):
        send_message(sender_socket, MESSAGE_FAILED, "server", sender, f"{receiver} has blocked you")
        print(f"{Fore.RED}[BLOCKED] {sender} -> {receiver} (blocked){Style.RESET_ALL}")
        return

    recipient_socket = get_online_client_socket(receiver)

    if recipient_socket:
        is_file = msg_type in [IMAGE, VIDEO_FILE, AUDIO_FILE, DOCUMENT]

        if is_file:
            filename = header.get("FILENAME", f"file_{get_timestamp()}")
            success = send_file(recipient_socket, msg_type, sender, receiver, filename, body)
        else:
            success = send_message(recipient_socket, msg_type, sender, receiver, body.decode("utf-8") if body else "")

        if success:
            send_message(sender_socket, ACK, "server", sender, f"Message delivered to {receiver}")
            print(f"{Fore.GREEN}[ROUTE] {msg_type} from {sender} to {receiver} delivered{Style.RESET_ALL}")
        else:
            send_message(sender_socket, MESSAGE_FAILED, "server", sender, f"Could not deliver to {receiver}")
            print(f"{Fore.RED}[ROUTE FAILED] {sender} -> {receiver}{Style.RESET_ALL}")
    else:
        # --- Reject file transfers to offline users ---
        # Binary files cannot be stored in SQLite alongside text messages.
        # Attempting to do so would silently corrupt the data - the sender
        # would receive a false ACK and the file would never arrive.
        # We send MESSAGE_FAILED so the sender knows to try again when the
        # recipient is online. Text messages still use store-and-forward as normal.
        if msg_type in (IMAGE, VIDEO_FILE, AUDIO_FILE, DOCUMENT):
            send_message(sender_socket, MESSAGE_FAILED, "server", sender,
                         f"{receiver} is offline. File transfers require the recipient to be online.")
            print(f"{Fore.YELLOW}[FILE REJECTED] {msg_type} from {sender} -> {receiver} (offline){Style.RESET_ALL}")
        else:
            body_text = body.decode("utf-8") if body else ""
            save_message(sender, receiver, msg_type, body_text, get_timestamp())
            send_message(sender_socket, ACK, "server", sender, f"{receiver} is offline. Message stored.")
            print(f"{Fore.CYAN}[STORE] {receiver} offline. Message from {sender} stored{Style.RESET_ALL}")


def route_group_message(header, body, sender_socket):
    """
    Routes a message to all members of a group.
    Sends to every online member except the sender.
    Stores for offline members.
    """
    sender = header.get(FIELD_FROM)
    group_name = header.get(FIELD_TO)
    body_text = body.decode("utf-8") if body else ""

    members = get_group_members(group_name)

    if not members:
        send_message(sender_socket, ERROR, "server", sender, f"Group '{group_name}' not found or empty")
        return

    delivered = 0
    stored = 0
    blocked = 0

    for member in members:
        if member == sender:
            continue
        if is_blocked(member, sender):
            blocked += 1
            continue  # skip silently, don't deliver to this member
        sock = get_online_client_socket(member)
        if sock:
            send_message(sock, TEXT, sender, member, f"[{group_name}] {body_text}")
            delivered += 1
        else:
            save_message(sender, member, TEXT, f"[{group_name}] {body_text}", get_timestamp())
            stored += 1

    send_message(sender_socket, ACK, "server", sender, f"Group message sent to {delivered} member(s)")
    print(
        f"{Fore.MAGENTA}[GROUP] {sender} sent message to group '{group_name}' (delivered: {delivered}, stored: {stored}, blocked: {blocked}){Style.RESET_ALL}")


def handle_p2p_register(username, client_socket, body):
    """
    Store the client's P2P listen port after login.
    The IP comes from the TCP connection, not the message body, to prevent spoofing.
    """
    try:
        p2p_port = int(body.decode("utf-8").strip())
        ip = client_socket.getpeername()[0]
        register_p2p(username, ip, p2p_port)
        send_message(client_socket, ACK, "server", username, f"P2P registered on {ip}:{p2p_port}")
        print(f"{Fore.MAGENTA}[P2P] {username} registered at {ip}:{p2p_port}{Style.RESET_ALL}")
    except Exception as e:
        send_message(client_socket, ERROR, "server", username, f"P2P registration failed: {e}")
        print(f"{Fore.RED}[P2P ERROR] {username} registration failed: {e}{Style.RESET_ALL}")


def handle_p2p_request(username, client_socket, header, body):
    """
    Broker a direct file transfer: exchange addresses and step out.
    Sends P2P_SIGNAL to the sender with the peer's IP:port.
    Sends P2P_INCOMING to the receiver so it knows to expect the connection.
    Sends P2P_DENIED if the peer is offline - file transfers require both
    users to be online since binary files cannot be stored for later delivery.

    Body format: <filename>\\n<filepath>\\n<filesize>
    """
    receiver = header.get(FIELD_TO)
    try:
        parts = body.decode("utf-8").strip().split("\n")
        filename = parts[0] if len(parts) > 0 else "file"
        filepath = parts[1] if len(parts) > 1 else ""
        filesize = parts[2] if len(parts) > 2 else "0"
    except Exception:
        filename = filepath = "";
        filesize = "0"

    peer_info = get_p2p_info(receiver)
    peer_sock = get_online_client_socket(receiver)

    if not peer_info or not peer_sock:
        # server routing cannot store binary files for offline delivery either.
        # New message tells the sender exactly what they need to do.
        send_message(client_socket, P2P_DENIED, "server", username,
                     f"{receiver} is offline. File transfers require the recipient to be online.")
        print(f"{Fore.YELLOW}[P2P DENIED] {username} -> {receiver} (offline){Style.RESET_ALL}")
        return

    peer_ip, peer_port = peer_info

    send_message(client_socket, P2P_SIGNAL, "server", username,
                 f"IP: {peer_ip}\nPort: {peer_port}\nUsername: {receiver}\n"
                 f"Filename: {filename}\nFilepath: {filepath}\nFilesize: {filesize}")

    sender_info = get_p2p_info(username)
    sender_ip = sender_info[0] if sender_info else client_socket.getpeername()[0]
    send_message(peer_sock, P2P_INCOMING, "server", receiver,
                 f"IP: {sender_ip}\nUsername: {username}\nFilename: {filename}\nFilesize: {filesize}")

    print(
        f"{Fore.MAGENTA}[P2P] Signalled {Fore.CYAN}{username}{Fore.MAGENTA} -> {Fore.CYAN}{receiver}{Fore.MAGENTA} ({filename}){Style.RESET_ALL}")


def handle_client(client_socket, client_address):
    """
    The main loop for one connected client.
    Reads messages one at a time and routes each based on its TYPE field.
    The finally block always runs to clean up on exit or crash.
    """
    print(f"{Fore.CYAN}[CONNECT] New connection from {client_address}{Style.RESET_ALL}")
    buf = bytearray()
    username = None

    try:
        while True:
            header, body, buf = receive_full_message(client_socket, buf)

            if header is None:
                print(f"{Fore.RED}[DISCONNECT] {username or client_address} lost connection{Style.RESET_ALL}")
                break

            msg_type = header.get(FIELD_TYPE)

            # Format timestamp for logging
            timestamp = datetime.now().strftime("%H:%M:%S")

            if msg_type == REGISTER:
                username_reg = header.get(FIELD_FROM)
                password_reg = body.decode("utf-8").replace("password: ", "").strip() if body else ""
                print(
                    f"{Fore.CYAN}[{timestamp}] [RECV] {Fore.YELLOW}{msg_type}{Fore.CYAN} from {Fore.GREEN}{username_reg}{Style.RESET_ALL}")

                if not username_reg or not password_reg:
                    send_message(client_socket, ERROR, "server", "unknown", "Username and password required")
                    print(f"{Fore.RED}[REGISTER] Failed: Missing credentials{Style.RESET_ALL}")
                elif register_user(username_reg, password_reg):
                    send_message(client_socket, ACK, "server", username_reg,
                                 "Registration successful. You can now log in.")
                    print(f"{Fore.GREEN}[REGISTER] New user '{username_reg}' registered{Style.RESET_ALL}")
                else:
                    send_message(client_socket, ERROR, "server", username_reg, "Username already taken")
                    print(f"{Fore.YELLOW}[REGISTER] Username '{username_reg}' already taken{Style.RESET_ALL}")

            elif msg_type == LOGIN:
                print(
                    f"{Fore.GREEN}[{timestamp}] [RECV] {Fore.YELLOW}{msg_type}{Fore.GREEN} from {Fore.CYAN}{header.get(FIELD_FROM, '?')}{Style.RESET_ALL}")
                username = handle_login(client_socket, client_address, header, body)
                if username is None:
                    break
                # After successful login, continue waiting for messages
                continue

            elif msg_type == LOGOUT:
                print(
                    f"{Fore.YELLOW}[{timestamp}] [RECV] {Fore.YELLOW}{msg_type}{Fore.YELLOW} from {Fore.CYAN}{username}{Style.RESET_ALL}")
                send_message(client_socket, ACK, "server", username, "Logged out")
                break

            elif msg_type == P2P_REGISTER:
                if username:
                    print(
                        f"{Fore.MAGENTA}[{timestamp}] [RECV] {Fore.YELLOW}{msg_type}{Fore.MAGENTA} from {Fore.GREEN}{username}{Style.RESET_ALL}")
                    handle_p2p_register(username, client_socket, body)

            elif msg_type == P2P_REQUEST:
                if username:
                    print(
                        f"{Fore.MAGENTA}[{timestamp}] [RECV] {Fore.YELLOW}{msg_type}{Fore.MAGENTA} from {Fore.GREEN}{username}{Style.RESET_ALL}")
                    handle_p2p_request(username, client_socket, header, body)

            elif msg_type in [TEXT, IMAGE, VIDEO_FILE, AUDIO_FILE, DOCUMENT]:
                # Print received message with appropriate color based on type
                if msg_type == TEXT:
                    print(
                        f"{Fore.CYAN}[{timestamp}] [RECV] {Fore.YELLOW}{msg_type}{Fore.CYAN} from {Fore.GREEN}{username}{Style.RESET_ALL}")
                else:
                    print(
                        f"{Fore.MAGENTA}[{timestamp}] [RECV] {Fore.YELLOW}{msg_type}{Fore.MAGENTA} from {Fore.GREEN}{username}{Style.RESET_ALL}")
                route_message(header, body, client_socket)

            elif msg_type == "GROUP_MSG":
                print(
                    f"{Fore.MAGENTA}[{timestamp}] [RECV] {Fore.YELLOW}{msg_type}{Fore.MAGENTA} from {Fore.GREEN}{username}{Style.RESET_ALL}")
                route_group_message(header, body, client_socket)

            elif msg_type == BLOCK_USER:
                target = header.get(FIELD_TO)
                print(
                    f"{Fore.RED}[{timestamp}] [RECV] {Fore.YELLOW}{msg_type}{Fore.RED} from {Fore.GREEN}{username}{Fore.RED} -> {target}{Style.RESET_ALL}")
                block_user(username, target)
                send_message(client_socket, ACK, "server", username, f"{target} has been blocked")
                print(f"{Fore.RED}[BLOCK] {username} blocked {target}{Style.RESET_ALL}")

            elif msg_type == CREATE_GROUP:
                group_name = body.decode("utf-8").strip() if body else ""
                print(
                    f"{Fore.MAGENTA}[{timestamp}] [RECV] {Fore.YELLOW}{msg_type}{Fore.MAGENTA} from {Fore.GREEN}{username}{Fore.MAGENTA} -> {group_name}{Style.RESET_ALL}")
                success = create_group(group_name, username)
                if success:
                    send_message(client_socket, ACK, "server", username, f"Group '{group_name}' created")
                    print(f"{Fore.MAGENTA}[GROUP] {username} created '{group_name}'{Style.RESET_ALL}")
                else:
                    send_message(client_socket, ERROR, "server", username, f"Group '{group_name}' already exists")
                    print(f"{Fore.YELLOW}[GROUP] Group '{group_name}' already exists{Style.RESET_ALL}")

            elif msg_type == JOIN_GROUP:
                group_name = body.decode("utf-8").strip() if body else ""
                print(
                    f"{Fore.MAGENTA}[{timestamp}] [RECV] {Fore.YELLOW}{msg_type}{Fore.MAGENTA} from {Fore.GREEN}{username}{Fore.MAGENTA} -> {group_name}{Style.RESET_ALL}")
                add_to_group(group_name, username)
                send_message(client_socket, ACK, "server", username, f"Joined group '{group_name}'")
                print(f"{Fore.MAGENTA}[GROUP] {username} joined '{group_name}'{Style.RESET_ALL}")

            elif msg_type == ADD_USER:
                body_text = body.decode("utf-8").strip() if body else ""
                parts = body_text.split(":", 1)
                if len(parts) == 2:
                    group_name = parts[0].strip()
                    user_to_add = parts[1].strip()
                    print(
                        f"{Fore.MAGENTA}[{timestamp}] [RECV] {Fore.YELLOW}{msg_type}{Fore.MAGENTA} from {Fore.GREEN}{username}{Fore.MAGENTA} -> {user_to_add} to {group_name}{Style.RESET_ALL}")
                    add_to_group(group_name, user_to_add)
                    send_message(client_socket, ACK, "server", username, f"{user_to_add} added to '{group_name}'")
                    print(f"{Fore.MAGENTA}[GROUP] {username} added {user_to_add} to '{group_name}'{Style.RESET_ALL}")
                else:
                    send_message(client_socket, ERROR, "server", username, "Invalid ADD_USER format")
                    print(f"{Fore.RED}[ERROR] Invalid ADD_USER format from {username}{Style.RESET_ALL}")

            elif msg_type == REMOVE_USER:
                body_text = body.decode("utf-8").strip() if body else ""
                parts = body_text.split(":", 1)
                if len(parts) == 2:
                    group_name = parts[0].strip()
                    user_to_remove = parts[1].strip()
                    print(
                        f"{Fore.MAGENTA}[{timestamp}] [RECV] {Fore.YELLOW}{msg_type}{Fore.MAGENTA} from {Fore.GREEN}{username}{Fore.MAGENTA} -> remove {user_to_remove} from {group_name}{Style.RESET_ALL}")
                    remove_from_group(group_name, user_to_remove)
                    send_message(client_socket, ACK, "server", username,
                                 f"{user_to_remove} removed from '{group_name}'")
                    print(
                        f"{Fore.MAGENTA}[GROUP] {username} removed {user_to_remove} from '{group_name}'{Style.RESET_ALL}")
                else:
                    send_message(client_socket, ERROR, "server", username, "Invalid REMOVE_USER format")
                    print(f"{Fore.RED}[ERROR] Invalid REMOVE_USER format from {username}{Style.RESET_ALL}")

            elif msg_type == EXIT_GROUP:
                group_name = body.decode("utf-8").strip() if body else ""
                print(
                    f"{Fore.MAGENTA}[{timestamp}] [RECV] {Fore.YELLOW}{msg_type}{Fore.MAGENTA} from {Fore.GREEN}{username}{Fore.MAGENTA} -> {group_name}{Style.RESET_ALL}")
                remove_from_group(group_name, username)
                send_message(client_socket, ACK, "server", username, f"Left group '{group_name}'")
                print(f"{Fore.MAGENTA}[GROUP] {username} left '{group_name}'{Style.RESET_ALL}")

            else:
                print(
                    f"{Fore.YELLOW}[{timestamp}] [WARN] Unknown message type: {msg_type} from {username or 'unknown'}{Style.RESET_ALL}")
                send_message(client_socket, ERROR, "server", username or "unknown", f"Unknown message type: {msg_type}")

    except Exception as e:
        print(f"{Fore.RED}[ERROR] handle_client crashed for {username}: {e}{Style.RESET_ALL}")
        import traceback
        traceback.print_exc()

    finally:
        handle_logout(username)
        client_socket.close()
        print(f"{Fore.RED}[CLOSED] {username or client_address} connection closed.{Style.RESET_ALL}")


def start_server():
    """
    Creates the TCP server socket and starts accepting connections.
    Each new client gets its own thread running handle_client.
    """
    # Clear screen for better visibility
    os.system('cls' if os.name == 'nt' else 'clear')

    # Print beautiful banner
    print(f"{Fore.CYAN}{'═' * 60}{Style.RESET_ALL}")
    print(f"{Fore.CYAN}║{Fore.WHITE}{' ' * 58}{Fore.CYAN}║")
    print(f"{Fore.CYAN}║{Fore.YELLOW}{'CSC3002F CHAT SERVER'.center(58)}{Fore.CYAN}║")
    print(f"{Fore.CYAN}║{Fore.GREEN}{'Multi-Paradigm Chat Application'.center(58)}{Fore.CYAN}║")
    print(f"{Fore.CYAN}║{Fore.WHITE}{' ' * 58}{Fore.CYAN}║")
    print(f"{Fore.CYAN}{'═' * 60}{Style.RESET_ALL}")

    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind((HOST, TCP_PORT))
    server_socket.listen(MAX_CLIENTS)

    print(f"\n{Fore.GREEN}[SERVER] Listening on {Fore.YELLOW}{HOST}:{TCP_PORT}{Style.RESET_ALL}")
    print(f"{Fore.GREEN}[SERVER] Waiting for connections... (Ctrl+C to stop){Style.RESET_ALL}")
    print(f"{Fore.CYAN}{'─' * 60}{Style.RESET_ALL}\n")

    try:
        while True:
            client_socket, client_address = server_socket.accept()
            thread = threading.Thread(target=handle_client, args=(client_socket, client_address), daemon=True)
            thread.start()
            print(
                f"{Fore.GREEN}[SERVER] Active connections: {Fore.YELLOW}{threading.active_count() - 1}{Style.RESET_ALL}")

    except KeyboardInterrupt:
        print(f"\n{Fore.YELLOW}[SERVER] Shutting down{Style.RESET_ALL}")
    finally:
        server_socket.close()
        print(f"{Fore.RED}[SERVER] Stopped{Style.RESET_ALL}")


if __name__ == "__main__":
    from server.udp_relay import start_udp_relay

    udp_thread = threading.Thread(target=start_udp_relay, daemon=True)
    udp_thread.start()
    print(f"{Fore.GREEN}[SERVER] UDP relay started on port {Fore.YELLOW}9001{Style.RESET_ALL}")

    start_server()