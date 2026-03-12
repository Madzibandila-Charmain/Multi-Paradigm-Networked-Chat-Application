# A program which implements the client side of a Multi-Paradigm Chat Application
# Author: MADZIBANDILA CHARMAIN
# Date: 28 February 2026

import socket
import threading
import os
import sys
import time
from datetime import datetime

# Add Colorama imports
from colorama import init, Fore, Back, Style

init()  # Initialize colorama (automatically resets on Windows)

# Custom ANSI colors not available in colorama's built-in palette
SALMON = "\033[38;5;209m"   # salmon pink  — file, group, P2P operations
LBLUE  = "\033[38;5;117m"   # light blue   — prompts, info, incoming messages, help menu

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import (
    HOST, TCP_PORT, UDP_PORT, BUFFER_SIZE, MEDIA_DIR,
    LOGIN, LOGOUT, TEXT, IMAGE, VIDEO_FILE, AUDIO_FILE, DOCUMENT,
    ACK, ERROR, MESSAGE_FAILED, TYPING, USER_ONLINE, USER_OFFLINE,
    KEEP_ALIVE, BLOCK_USER, CREATE_GROUP, JOIN_GROUP, ADD_USER,
    REMOVE_USER, EXIT_GROUP,
    FIELD_TYPE, FIELD_FROM, FIELD_TO, FIELD_SIZE,
    HEADER_BODY_SEPARATOR, HEADER_FIELD_SEPARATOR, FIELD_TIMESTAMP
)
from utils.message import (
    build_tcp_message, parse_tcp_header,
    build_udp_message, parse_udp_message, get_timestamp
)
from client.file_transfer import (
    send_file, receive_file, detect_file_type
)

from constants import (
    P2P_REGISTER, P2P_REQUEST
)

class ClientHandler:

    def __init__(self):
        self.username = None
        self.keep_running = True

        # TCP Socket
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        # UDP Socket
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.udp_socket.bind(("0.0.0.0", 0))

        # P2P server socket for direct file transfers
        self.p2p_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.p2p_server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.p2p_server_socket.bind(("0.0.0.0", 0))
        self.p2p_server_socket.listen(5)
        self.p2p_port = self.p2p_server_socket.getsockname()[1]

    def connect(self):
        try:
            self.tcp_socket.connect((HOST, TCP_PORT))
            print(f"{Fore.LIGHTGREEN_EX}=== SERVER HANDSHAKE COMPLETE ==={Style.RESET_ALL}")
            print(f"{LBLUE}Connected to server at {Fore.LIGHTYELLOW_EX}{HOST}:{TCP_PORT}{Style.RESET_ALL}")
            print(f"{LBLUE}Communication channel open.{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.LIGHTRED_EX}=== CONNECTION FAILED ==={Style.RESET_ALL}")
            print(f"{Fore.LIGHTYELLOW_EX}Unable to establish connection to server.{Style.RESET_ALL}")
            print(f"{Fore.LIGHTYELLOW_EX}Please verify server availability.{Style.RESET_ALL}")
            sys.exit(1)

    def register(self):

        username = input(f"\n{LBLUE}Enter new username: {Style.RESET_ALL}").strip()
        password = input(f"\n{LBLUE}Enter password: {Style.RESET_ALL}").strip()

        if not username or not password:
            print(f"{Fore.LIGHTRED_EX}[ERROR] Username and password cannot be empty{Style.RESET_ALL}")
            return None

        # REGISTER message body
        body = f"password: {password}"
        msg = build_tcp_message(msg_type="REGISTER", sender=username, receiver="server", body=body)

        try:
            self.tcp_socket.sendall(msg.encode("utf-8"))
            print(f"{Fore.LIGHTGREEN_EX}Registration request sent{Style.RESET_ALL}")
        except Exception as e:
            print(f"{Fore.LIGHTRED_EX}[ERROR] Failed to send REGISTER: {e}{Style.RESET_ALL}")
            return None

        buffer = bytearray()
        registration_complete = False

        while True:
            try:
                chunk = self.tcp_socket.recv(4096)
                if not chunk:
                    print(f"{Fore.LIGHTRED_EX}[ERROR] Server closed connection{Style.RESET_ALL}")
                    return None

                buffer += chunk

                while HEADER_BODY_SEPARATOR.encode("utf-8") in buffer:
                    header_bytes, rest = buffer.split(HEADER_BODY_SEPARATOR.encode("utf-8"), 1)
                    header = parse_tcp_header(header_bytes.decode("utf-8"))

                    body_size = int(header.get("SIZE", 0))
                    if len(rest) < body_size:
                        break  # wait for full body

                    body_bytes = bytes(rest[:body_size])
                    buffer = bytearray(rest[body_size:])  # leftover for next message

                    msg_type = header.get("TYPE")
                    sender = header.get("FROM")
                    message_body = body_bytes.decode("utf-8") if body_bytes else ""

                    # Handle registration response
                    if not registration_complete:
                        if msg_type == "ACK":
                            print(f"{Fore.LIGHTGREEN_EX}[SUCCESS] {message_body or 'Registration successful'}{Style.RESET_ALL}")
                            registration_complete = True

                        elif msg_type == "ERROR":
                            print(f"{Fore.LIGHTRED_EX}[ERROR] {message_body or 'Registration failed'}{Style.RESET_ALL}")
                            return None

                        elif msg_type == "P2P_DENIED":
                            print(f"{Fore.LIGHTYELLOW_EX}[P2P DENIED] {message_body}{Style.RESET_ALL}")

                        elif msg_type == MESSAGE_FAILED:
                            print(f"{Fore.LIGHTYELLOW_EX}[FAILED] {message_body}{Style.RESET_ALL}")

                    # Handle any extra messages from server (like offline messages)
                    if registration_complete:
                        print(f"{LBLUE}[SERVER MESSAGE] {msg_type} from {sender}: {message_body}{Style.RESET_ALL}")

                if registration_complete:
                    # Once registration is acknowledged, break out and return
                    return username

            except Exception as e:
                print(f"{Fore.LIGHTRED_EX}[ERROR] Exception while waiting for server response: {e}{Style.RESET_ALL}")
                return None

    def login(self, username, password=""):
        self.username = username
        body = f"password: {password}"
        msg = build_tcp_message(LOGIN, username, "server", body)
        self.tcp_socket.sendall(msg.encode())
        print(f"{Fore.LIGHTGREEN_EX}Login request sent{Style.RESET_ALL}")

        buffer = b""

        while True:
            data = self.tcp_socket.recv(BUFFER_SIZE)
            if not data:
                print(f"{Fore.LIGHTRED_EX}[ERROR] Server disconnected during login{Style.RESET_ALL}")
                return False

            buffer += data

            while True:
                sep_index = buffer.find(HEADER_BODY_SEPARATOR.encode())
                if sep_index == -1:
                    break

                header_part = buffer[:sep_index]
                remaining = buffer[sep_index + len(HEADER_BODY_SEPARATOR):]
                parsed = parse_tcp_header(header_part.decode(errors="ignore"))
                if not parsed:
                    buffer = remaining
                    continue

                msg_type = parsed.get(FIELD_TYPE)
                size = int(parsed.get(FIELD_SIZE, 0))

                if len(remaining) < size:
                    break

                body_bytes = remaining[:size]
                buffer = remaining[size:]
                body_text = body_bytes.decode(errors="ignore")

                if msg_type == ACK:
                    print(f"{Fore.LIGHTGREEN_EX}Login successful{Style.RESET_ALL}")
                    register_msg = build_tcp_message(P2P_REGISTER, self.username, "server", str(self.p2p_port))
                    self.tcp_socket.sendall(register_msg.encode())
                    print(f"{SALMON}P2P port {self.p2p_port} registered{Style.RESET_ALL}")
                    return True

                elif msg_type == ERROR:
                    print(f"{Fore.LIGHTRED_EX}Login failed: {body_text}{Style.RESET_ALL}")
                    return False

    def logout(self):
        try:
            msg = build_tcp_message(LOGOUT, self.username, "server")
            self.tcp_socket.sendall(msg.encode())
        except:
            pass

        self.keep_running = False
        time.sleep(0.5)
        self.tcp_socket.close()
        self.udp_socket.close()
        self.p2p_server_socket.close()
        print(f"{Fore.LIGHTYELLOW_EX}Logged out. Goodbye.{Style.RESET_ALL}")
        sys.exit(0)

    def send_file(self, receiver, filepath):
        if not os.path.exists(filepath):
            print(f"{Fore.LIGHTRED_EX}[ERROR] File not found{Style.RESET_ALL}")
            return

        filesize = os.path.getsize(filepath)
        print(f"{SALMON}Preparing to send {os.path.basename(filepath)} ({filesize} bytes) to {receiver}{Style.RESET_ALL}")

        # Asks the server for P2P connection
        body = f"{os.path.basename(filepath)}\n{filepath}\n{filesize}"

        msg = build_tcp_message(P2P_REQUEST, self.username, receiver, body)

        self.tcp_socket.sendall(msg.encode())

        print(f"{SALMON}[P2P REQUEST] Requesting direct transfer to {receiver}{Style.RESET_ALL}")

    def send_text(self, receiver, text):
        msg = build_tcp_message(TEXT, self.username, receiver, text)
        self.tcp_socket.sendall(msg.encode())

    def send_group_message(self, group_name, text):
        msg = build_tcp_message("GROUP_MSG", self.username, group_name, text)
        self.tcp_socket.sendall(msg.encode())

    def create_group(self, group_name):
        msg = build_tcp_message(CREATE_GROUP, self.username, "server", group_name)
        self.tcp_socket.sendall(msg.encode())
        print(f"{SALMON}Creating group: {group_name}{Style.RESET_ALL}")

    def join_group(self, group_name):
        msg = build_tcp_message(JOIN_GROUP, self.username, "server", group_name)
        self.tcp_socket.sendall(msg.encode())
        print(f"{SALMON}Joining group: {group_name}{Style.RESET_ALL}")

    def add_user(self, group_name, user_to_add):
        if user_to_add == self.username:
            print(f"{Fore.LIGHTRED_EX}[GROUP ERROR] You cannot add yourself to a group you created.{Style.RESET_ALL}")
            return

        body = f"{group_name}:{user_to_add}"
        msg = build_tcp_message(ADD_USER, self.username, "server", body)
        self.tcp_socket.sendall(msg.encode())
        print(f"{SALMON}Adding {user_to_add} to group {group_name}{Style.RESET_ALL}")

    def remove_user(self, group_name, user_to_remove):
        body = f"{group_name}:{user_to_remove}"
        msg = build_tcp_message(REMOVE_USER, self.username, "server", body)
        self.tcp_socket.sendall(msg.encode())

    def exit_group(self, group_name):
        msg = build_tcp_message(EXIT_GROUP, self.username, "server", group_name)
        self.tcp_socket.sendall(msg.encode())
        print(f"{Fore.LIGHTYELLOW_EX}Leaving group: {group_name}{Style.RESET_ALL}")

    def block_user(self, target_user):
        msg = build_tcp_message(BLOCK_USER, self.username, target_user, "")
        self.tcp_socket.sendall(msg.encode())
        print(f"{Fore.LIGHTRED_EX}Blocking user: {target_user}{Style.RESET_ALL}")

    def _do_p2p_send(self, peer_ip, peer_port, peer_username, filename, filepath):
        try:
            p2p_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            p2p_socket.connect((peer_ip, peer_port))

            file_type = detect_file_type(filename)
            size      = os.path.getsize(filepath)

            header = (
                f"TYPE: {file_type}{HEADER_FIELD_SEPARATOR}"
                f"FROM: {self.username}{HEADER_FIELD_SEPARATOR}"
                f"TO: {peer_username}{HEADER_FIELD_SEPARATOR}"
                f"TIMESTAMP: {get_timestamp()}{HEADER_FIELD_SEPARATOR}"
                f"FILENAME: {filename}{HEADER_FIELD_SEPARATOR}"
                f"SIZE: {size}"
                f"{HEADER_BODY_SEPARATOR}"
            )
            p2p_socket.sendall(header.encode())

            with open(filepath, "rb") as f:
                while True:
                    chunk = f.read(BUFFER_SIZE)
                    if not chunk:
                        break
                    p2p_socket.sendall(chunk)

            p2p_socket.close()
            print(f"{Fore.LIGHTGREEN_EX}[P2P SENT] {filename}{Style.RESET_ALL}")

        except Exception as e:
            print(f"{Fore.LIGHTRED_EX}[P2P ERROR] {e}{Style.RESET_ALL}")

    def receive_messages(self):
        buffer = b""

        while self.keep_running:
            try:
                data = self.tcp_socket.recv(BUFFER_SIZE)

                if not data:
                    print(f"{Fore.LIGHTRED_EX}[SERVER DISCONNECTED]{Style.RESET_ALL}")
                    self.keep_running = False  # stop threads
                    break

                buffer += data

                while True:

                    sep_index = buffer.find(HEADER_BODY_SEPARATOR.encode())

                    if sep_index == -1:
                        break

                    header_part = buffer[:sep_index]
                    remaining = buffer[sep_index + len(HEADER_BODY_SEPARATOR):]

                    header_text = header_part.decode(errors="ignore")
                    parsed = parse_tcp_header(header_text)

                    if not parsed:
                        buffer = remaining
                        continue

                    msg_type = parsed.get(FIELD_TYPE)
                    size = int(parsed.get(FIELD_SIZE, 0))

                    if len(remaining) < size:
                        break

                    body_bytes = remaining[:size]
                    buffer = remaining[size:]
                    body = body_bytes.decode(errors="ignore")

                    # Format timestamp
                    timestamp = parsed.get(FIELD_TIMESTAMP, "")
                    if timestamp:
                        try:
                            dt = datetime.fromisoformat(timestamp)
                            time_str = dt.strftime("%H:%M:%S")
                        except:
                            time_str = timestamp.split('T')[-1] if 'T' in timestamp else timestamp
                    else:
                        time_str = ""

                    if msg_type in (IMAGE, VIDEO_FILE, AUDIO_FILE, DOCUMENT):
                        filename = parsed.get('FILENAME', 'unknown')
                        print(f"{SALMON}[{time_str}] Receiving file: {filename}{Style.RESET_ALL}")
                        receive_file(parsed, body_bytes)

                    elif msg_type == "P2P_SIGNAL":
                        lines = body.split("\n")
                        try:
                            peer_ip       = lines[0].split(": ", 1)[1]
                            peer_port     = int(lines[1].split(": ", 1)[1])
                            peer_username = lines[2].split(": ", 1)[1]
                            filename      = lines[3].split(": ", 1)[1]
                            filepath      = lines[4].split(": ", 1)[1]
                        except Exception:
                            print(f"{Fore.LIGHTRED_EX}[P2P ERROR] Malformed P2P_SIGNAL message{Style.RESET_ALL}")
                            continue

                        print(f"{SALMON}[P2P] Direct connection ready with {Fore.LIGHTGREEN_EX}{peer_username}{SALMON} at {peer_ip}:{peer_port}{Style.RESET_ALL}")

                        threading.Thread(target=self._do_p2p_send, args=(peer_ip, peer_port, peer_username, filename, filepath), daemon=True).start()

                    elif msg_type == "P2P_INCOMING":
                        lines = body.split("\n")

                        try:
                            peer_ip = lines[0].split(": ", 1)[1]
                            peer_username = lines[1].split(": ", 1)[1]
                            filename = lines[2].split(": ", 1)[1]
                        except Exception:
                            print(f"{Fore.LIGHTRED_EX}[P2P ERROR] Malformed P2P_INCOMING message{Style.RESET_ALL}")
                            continue

                        print(f"{SALMON}[P2P] {Fore.LIGHTGREEN_EX}{peer_username}{SALMON} is sending you file: {Fore.LIGHTYELLOW_EX}{filename}{Style.RESET_ALL}")

                    elif msg_type == "P2P_DENIED":
                        print(f"{Fore.LIGHTYELLOW_EX}[FILE FAILED] {body}{Style.RESET_ALL}")

                    elif msg_type == ACK:
                        print(f"{Fore.LIGHTGREEN_EX}[{time_str}] [ACK] {body}{Style.RESET_ALL}")

                    elif msg_type == ERROR:
                        print(f"{Fore.LIGHTRED_EX}[{time_str}] [ERROR] {body}{Style.RESET_ALL}")

                    elif msg_type == MESSAGE_FAILED:
                        print(f"{Fore.LIGHTYELLOW_EX}[{time_str}] [FAILED] {body}{Style.RESET_ALL}")

                    elif msg_type == USER_ONLINE:
                        print(f"{Fore.LIGHTGREEN_EX}[{time_str}] [+] {parsed.get('FROM', '?')} is now online{Style.RESET_ALL}")

                    elif msg_type == USER_OFFLINE:
                        print(f"{Fore.LIGHTRED_EX}[{time_str}] [-] {parsed.get('FROM', '?')} has gone offline{Style.RESET_ALL}")

                    #elif msg_type == "GROUP_ADDED":
                        #print(f"{SALMON}[GROUP] {body}{Style.RESET_ALL}")

                    else:
                        sender = parsed.get('FROM', '?')
                        is_self = (sender == self.username)

                        if is_self:
                            print()
                            print(f"{Fore.LIGHTGREEN_EX}┌─ You [{time_str}]{Style.RESET_ALL}")
                            print(f"{Fore.LIGHTGREEN_EX}│{Style.RESET_ALL} {body}")
                            print(f"{Fore.LIGHTGREEN_EX}└{'─' * 40}{Style.RESET_ALL}")
                        else:
                            # Check if it's a group message
                            if body.startswith('[') and ']' in body:
                                # Group message format: [group] message
                                group_end = body.find(']')
                                group_name = body[1:group_end]
                                actual_msg = body[group_end + 1:].strip()
                                print()
                                print(f"{SALMON}┌─ [{sender}] → [{group_name}] @ {time_str}{Style.RESET_ALL}")
                                print(f"{SALMON}│{Style.RESET_ALL} {actual_msg}")
                                print(f"{SALMON}└{'─' * 40}{Style.RESET_ALL}")
                            else:
                                print()
                                print(f"{LBLUE}┌─ {sender} @ {time_str}{Style.RESET_ALL}")
                                print(f"{LBLUE}│{Style.RESET_ALL} {body}")
                                print(f"{LBLUE}└{'─' * 40}{Style.RESET_ALL}")

            except Exception as e:
                if self.keep_running:
                    error_msg = str(e)
                    print()
                    print(f"{Fore.LIGHTRED_EX}┌─[ERROR] NETWORK EXCEPTION")
                    print(f"│ {error_msg}")
                    print(f"└{'─' * len(error_msg)}{Style.RESET_ALL}\n")

                break

    def p2p_thread(self):
        while self.keep_running:
            try:
                conn, addr = self.p2p_server_socket.accept()
                print(f"{SALMON}[P2P] Incoming connection from {addr}{Style.RESET_ALL}")

                threading.Thread(
                    target=self.handle_p2p_transfer,
                    args=(conn, addr),
                    daemon=True
                ).start()

            except Exception as e:
                if self.keep_running:
                    print(f"{Fore.LIGHTRED_EX}[P2P ERROR] {e}{Style.RESET_ALL}")
                break

    def handle_p2p_transfer(self, conn, addr):
        try:

            buffer = b""

            # Read header
            while HEADER_BODY_SEPARATOR.encode() not in buffer:
                chunk = conn.recv(BUFFER_SIZE)

                if not chunk:
                    conn.close()
                    return

                buffer += chunk

            header_part, remaining = buffer.split(HEADER_BODY_SEPARATOR.encode(), 1)
            parsed = parse_tcp_header(header_part.decode())

            filename = parsed.get("FILENAME", "unknown_file")
            size = int(parsed.get(FIELD_SIZE, 0))

            print(f"{SALMON}[P2P] Receiving file: {filename} ({size} bytes){Style.RESET_ALL}")

            os.makedirs(MEDIA_DIR, exist_ok=True)
            save_path = os.path.join(MEDIA_DIR, filename)

            received = len(remaining)

            # Write initial leftover bytes
            with open(save_path, "wb") as f:

                if remaining:
                    f.write(remaining)

                # Stream remaining file data
                while received < size:

                    chunk = conn.recv(BUFFER_SIZE)

                    if not chunk:
                        break

                    f.write(chunk)
                    received += len(chunk)

            print(f"{Fore.LIGHTGREEN_EX}[P2P RECEIVED] {filename}{Style.RESET_ALL}")

            conn.close()

        except Exception as e:
            print(f"{Fore.LIGHTRED_EX}[P2P TRANSFER ERROR] {e}{Style.RESET_ALL}")
            conn.close()

    def receive_udp(self):
        while self.keep_running:
            try:
                data, _ = self.udp_socket.recvfrom(BUFFER_SIZE)
                parsed = parse_udp_message(data.decode())
                if not parsed:
                    continue

                msg_type = parsed.get("TYPE")
                sender = parsed.get("FROM")

                if msg_type == TYPING:
                    print(f"{LBLUE} {sender} is typing... {Style.RESET_ALL}")

                elif msg_type == KEEP_ALIVE:
                    # Ignore keep-alive messages
                    pass

                else:
                    print(f"{Fore.LIGHTYELLOW_EX}[UDP] {msg_type} from {sender}{Style.RESET_ALL}")

            except Exception as e:
                if self.keep_running:
                    print(f"{Fore.LIGHTRED_EX}[UDP ERROR] {e}{Style.RESET_ALL}")
                break

    def send_typing(self, receiver):
        msg = build_udp_message(TYPING, self.username, receiver)
        self.udp_socket.sendto(msg.encode(), (HOST, UDP_PORT))

    def send_keep_alive(self):
        while self.keep_running:
            try:
                msg = build_udp_message(KEEP_ALIVE, self.username, "server")
                self.udp_socket.sendto(msg.encode(), (HOST, UDP_PORT))
                time.sleep(30)
            except:
                break

    def tcp_thread(self):
        thread = threading.Thread(target=self.receive_messages)
        thread.daemon = True
        thread.start()

    def udp_thread(self):
        thread = threading.Thread(target=self.receive_udp)
        thread.daemon = True
        thread.start()

    def keep_alive_thread(self):
        thread = threading.Thread(target=self.send_keep_alive)
        thread.daemon = True
        thread.start()

    def start_p2p_thread(self):
        thread = threading.Thread(target=self.p2p_thread)
        thread.daemon = True
        thread.start()

    def start_threads(self):
        self.tcp_thread()
        self.udp_thread()
        self.keep_alive_thread()
        self.start_p2p_thread()


if __name__ == "__main__":
    # Clear screen for better visibility
    os.system('cls' if os.name == 'nt' else 'clear')

    # Print banner
    print(f"{LBLUE}{'═' * 60}{Style.RESET_ALL}")
    print(f"{LBLUE}║{' ' * 58}║{Style.RESET_ALL}")
    print(f"{LBLUE}║{Fore.LIGHTYELLOW_EX}{'CSC3002F CHAT CLIENT'.center(58)}{LBLUE}║{Style.RESET_ALL}")
    print(f"{LBLUE}║{Fore.LIGHTGREEN_EX}{'Multi-Paradigm Chat Application'.center(58)}{LBLUE}║{Style.RESET_ALL}")
    print(f"{LBLUE}║{' ' * 58}║{Style.RESET_ALL}")
    print(f"{LBLUE}{'═' * 60}{Style.RESET_ALL}\n")

    client = ClientHandler()
    client.connect()

    while True:

        print(f"\n{Fore.LIGHTGREEN_EX}1. Register{Style.RESET_ALL}")
        print(f"{LBLUE}2. Login{Style.RESET_ALL}")
        print(f"{Fore.LIGHTRED_EX}3. Exit{Style.RESET_ALL}")

        choice = input(f"\n{Fore.LIGHTYELLOW_EX}Select option (1, 2, or 3): {Style.RESET_ALL}")

        # Validate menu input
        if choice not in ["1", "2", "3"]:
            print(f"{Fore.LIGHTRED_EX}Invalid option. Please select 1(Register), 2(Login), or 3(Exit).{Style.RESET_ALL}")
            continue

        if choice == "3":
            print(f"{Fore.LIGHTYELLOW_EX}Exiting client...{Style.RESET_ALL}")
            sys.exit(0)

        if choice == "1":
            registered_username = client.register()

            if not registered_username:
                print(f"{Fore.LIGHTRED_EX}Registration failed. Please try again.{Style.RESET_ALL}")
                continue

            print(f"{Fore.LIGHTGREEN_EX}You can now log in with your new credentials.{Style.RESET_ALL}")
            username = registered_username
            password = input(f"\n{LBLUE}Enter password: {Style.RESET_ALL}").strip()

            login_success = client.login(username, password)
            if not login_success:
                print(f"{Fore.LIGHTRED_EX}Login failed. Returning to main menu.{Style.RESET_ALL}")
                continue

            break

        elif choice == "2":

            username = input(f"{LBLUE}Enter username: {Style.RESET_ALL}").strip()
            password = input(f"{LBLUE}Enter password: {Style.RESET_ALL}").strip()

            login_success = client.login(username, password)

            if not login_success:
                print(f"{Fore.LIGHTRED_EX}Login failed. Please try again.{Style.RESET_ALL}")
                continue

            break

    # Only runs after successful login
    client.start_threads()

    print(f"\n  {Fore.LIGHTGREEN_EX}logged in as: {Fore.LIGHTYELLOW_EX}{username}{Style.RESET_ALL}\n")
    print(f"  {LBLUE}/msg  <user> <text>      send a message{Style.RESET_ALL}")
    print(f"  {SALMON}/file <user> <path>      send a file{Style.RESET_ALL}")
    print(f"  {SALMON}/gmsg <group> <text>     group message{Style.RESET_ALL}")
    print(f"  {SALMON}/create <group>          create a group{Style.RESET_ALL}")
    print(f"  {SALMON}/join  <group>           join a group{Style.RESET_ALL}")
    print(f"  {SALMON}/add   <group> <user>    add to group{Style.RESET_ALL}")
    print(f"  {SALMON}/remove <group> <user>   remove from group{Style.RESET_ALL}")
    print(f"  {SALMON}/leave <group>           leave a group{Style.RESET_ALL}")
    print(f"  {Fore.LIGHTRED_EX}/block <user>            block a user{Style.RESET_ALL}")
    print(f"  {Fore.LIGHTYELLOW_EX}/exit                    quit{Style.RESET_ALL}")
    print()

    while True:
        try:
            command = input(f"\n{Fore.LIGHTGREEN_EX}>>{Style.RESET_ALL} ")

            if not command.strip():
                continue

            if command.startswith("/msg"):
                parts = command.split(" ", 2)
                if len(parts) == 3:
                    client.send_text(parts[1], parts[2])
                else:
                    print(f"{Fore.LIGHTRED_EX}Usage: /msg <username> <text>{Style.RESET_ALL}")

            elif command.startswith("/file"):
                parts = command.split(" ", 2)
                if len(parts) == 3:
                    client.send_file(parts[1], parts[2])
                else:
                    print(f"{Fore.LIGHTRED_EX}Usage: /file <username> <path>{Style.RESET_ALL}")

            elif command.startswith("/block"):
                parts = command.split()
                if len(parts) == 2:
                    client.block_user(parts[1])
                else:
                    print(f"{Fore.LIGHTRED_EX}Usage: /block <username>{Style.RESET_ALL}")

            elif command.startswith("/create"):
                parts = command.split()
                if len(parts) == 2:
                    client.create_group(parts[1])
                else:
                    print(f"{Fore.LIGHTRED_EX}Usage: /create <group_name>{Style.RESET_ALL}")

            elif command.startswith("/add"):
                parts = command.split()
                if len(parts) == 3:
                    client.add_user(parts[1], parts[2])
                else:
                    print(f"{Fore.LIGHTRED_EX}Usage: /add <group_name> <username>{Style.RESET_ALL}")

            elif command.startswith("/remove"):
                parts = command.split()
                if len(parts) == 3:
                    client.remove_user(parts[1], parts[2])
                else:
                    print(f"{Fore.LIGHTRED_EX}Usage: /remove <group_name> <username>{Style.RESET_ALL}")

            elif command.startswith("/gmsg"):
                parts = command.split(" ", 2)
                if len(parts) == 3:
                    client.send_group_message(parts[1], parts[2])
                else:
                    print(f"{Fore.LIGHTRED_EX}Usage: /gmsg <group_name> <text>{Style.RESET_ALL}")

            elif command.startswith("/join"):
                parts = command.split()
                if len(parts) == 2:
                    client.join_group(parts[1])
                else:
                    print(f"{Fore.LIGHTRED_EX}Usage: /join <group_name>{Style.RESET_ALL}")

            elif command.startswith("/leave"):
                parts = command.split()
                if len(parts) == 2:
                    client.exit_group(parts[1])
                else:
                    print(f"{Fore.LIGHTRED_EX}Usage: /leave <group_name>{Style.RESET_ALL}")

            elif command.startswith("/exit"):
                client.logout()

            else:
                print(f"{Fore.LIGHTRED_EX}Unknown command. Type /msg, /gmsg, /file, /block, /create, /add, /remove, /join, /leave, or /exit{Style.RESET_ALL}")

        except KeyboardInterrupt:
            print(f"\n{Fore.LIGHTYELLOW_EX}Logging out...{Style.RESET_ALL}")
            client.logout()
            break
        except Exception as e:
            print(f"{Fore.LIGHTRED_EX}Error: {e}{Style.RESET_ALL}")