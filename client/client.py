# A program which implements the client side of a Multi-Paradigm Chat Application
# Author: MADZIBANDILA CHARMAIN
# Date: 28 February 2026

import socket
import threading
import os
import sys
import time

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
from client.file_transfer import send_file, receive_file, detect_file_type

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
        self.p2p_server_socket.bind(("0.0.0.0", 0))
        self.p2p_server_socket.listen(5)
        self.p2p_port = self.p2p_server_socket.getsockname()[1]

    def connect(self):
        try:
            self.tcp_socket.connect((HOST, TCP_PORT))
            print("=== SERVER HANDSHAKE COMPLETE ===")
            print(f"Connected to server at {HOST}:{TCP_PORT}")
            print("Communication channel open.")
        except Exception as e:
            print("=== CONNECTION FAILED ===")
            print("Unable to establish connection to server.")
            print("Please verify server availability.")

    def login(self, username, password=""):
        self.username = username
        body = f"password: {password}"
        msg = build_tcp_message(LOGIN, username, "server", body)
        self.tcp_socket.sendall(msg.encode())

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
        sys.exit(0)

    def send_file(self, receiver, filepath):
        send_file(self.tcp_socket, self.username, receiver, filepath)

    def send_text(self, receiver, text):
        msg = build_tcp_message(TEXT, self.username, receiver, text)
        self.tcp_socket.sendall(msg.encode())

    def send_group_message(self, group_name, text):
        msg = build_tcp_message("GROUP_MSG", self.username, group_name, text)
        self.tcp_socket.sendall(msg.encode())

    def create_group(self, group_name):
        msg = build_tcp_message(CREATE_GROUP, self.username, "server", group_name)
        self.tcp_socket.sendall(msg.encode())

    def join_group(self, group_name):
        msg = build_tcp_message(JOIN_GROUP, self.username, "server", group_name)
        self.tcp_socket.sendall(msg.encode())

    def add_user(self, group_name, user_to_add):
        # body format: "group_name:username" so server can extract both
        body = f"{group_name}:{user_to_add}"
        msg = build_tcp_message(ADD_USER, self.username, "server", body)
        self.tcp_socket.sendall(msg.encode())

    def remove_user(self, group_name, user_to_remove):
        body = f"{group_name}:{user_to_remove}"
        msg = build_tcp_message(REMOVE_USER, self.username, "server", body)
        self.tcp_socket.sendall(msg.encode())

    def exit_group(self, group_name):
        msg = build_tcp_message(EXIT_GROUP, self.username, "server", group_name)
        self.tcp_socket.sendall(msg.encode())

    def block_user(self, target_user):
        msg = build_tcp_message(BLOCK_USER, self.username, target_user)
        self.tcp_socket.sendall(msg.encode())

    def receive_messages(self):
        buffer = b""

        while self.keep_running:
            try:
                data = self.tcp_socket.recv(BUFFER_SIZE)

                if not data:
                    print("[SERVER DISCONNECTED]")
                    break

                buffer += data

                while HEADER_BODY_SEPARATOR.encode() in buffer:
                    header_part, buffer = buffer.split(HEADER_BODY_SEPARATOR.encode(), 1)
                    header_text = header_part.decode()
                    parsed = parse_tcp_header(header_text)

                    if not parsed:
                        continue

                    msg_type = parsed[FIELD_TYPE]
                    size = int(parsed.get(FIELD_SIZE, 0))

                    if len(buffer) < size:
                        buffer = header_part + HEADER_BODY_SEPARATOR.encode() + buffer
                        break

                    body_bytes = buffer[:size]
                    buffer = buffer[size:]
                    body = body_bytes.decode(errors="ignore")

                    if msg_type in (IMAGE, VIDEO_FILE, AUDIO_FILE, DOCUMENT):
                        receive_file(parsed, body_bytes)

                    elif msg_type == "P2P_SIGNAL":
                        lines = body.split("\n")
                        peer_ip = lines[0].split(": ")[1]
                        peer_username = lines[1].split(": ")[1]
                        print(f"\n[P2P] Direct connection ready with {peer_username} at {peer_ip}")

                    elif msg_type == ACK:
                        print(f">> [ACK] {body}")

                    elif msg_type == ERROR:
                        print(f">> [ERROR] {body}")

                    elif msg_type == MESSAGE_FAILED:
                        print(f">> [FAILED] {body}")

                    elif msg_type == USER_ONLINE:
                        print(f"\n[+] {parsed['FROM']} is now online")

                    elif msg_type == USER_OFFLINE:
                        print(f"\n[-] {parsed['FROM']} has gone offline")

                    else:
                        print(f"\n┌─[{parsed['FROM']}] @ {parsed['TIMESTAMP']}")
                        print(f"| {body}")
                        print("└" + "─" * (len(str(body)) + 2))

            except Exception as e:
                if self.keep_running:
                    error_msg = str(e)
                    print(f"\n┌─[ERROR] NETWORK EXCEPTION")
                    print(f"│ {error_msg}")
                    print("└" + "─" * len(error_msg) + "\n")
                break

    def p2p_thread(self):
        while self.keep_running:
            try:
                conn, addr = self.p2p_server_socket.accept()

                header_data = b""
                while HEADER_BODY_SEPARATOR.encode() not in header_data:
                    header_data += conn.recv(1)

                header_part = header_data.split(HEADER_BODY_SEPARATOR.encode())[0]
                parsed = parse_tcp_header(header_part.decode())
                size = int(parsed.get(FIELD_SIZE, 0))

                file_bytes = b""
                while len(file_bytes) < size:
                    file_bytes += conn.recv(BUFFER_SIZE)

                receive_file(parsed, file_bytes)
                conn.close()
            except:
                break

    def receive_udp(self):
        while self.keep_running:
            try:
                data, _ = self.udp_socket.recvfrom(BUFFER_SIZE)
                parsed = parse_udp_message(data.decode())
                if parsed:
                    print(f"\n[UDP] {parsed['TYPE']} from {parsed['FROM']}")
            except:
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

    client = ClientHandler()
    client.connect()

    username = input("Enter username: ")
    password = input("Enter password: ")
    client.login(username, password)

    client.start_threads()

    print("\n========================================")
    print("     Welcome to CSC3002F Chat App       ")
    print("========================================")
    print("  /msg <user> <text>          - Send a message")
    print("  /file <user> <path>         - Send a file")
    print("  /block <user>               - Block a user")
    print("  /create <group>             - Create a group")
    print("  /add <group> <user>         - Add user to group")
    print("  /gmsg <group> <text>        - Send group message")
    print("  /join <group>               - Join a group")
    print("  /leave <group>              - Leave a group")
    print("  /exit                       - Quit")
    print("========================================\n")

    while True:
        command = input(">> ")

        if not command.strip():
            continue

        if command.startswith("/msg"):
            parts = command.split(" ", 2)
            if len(parts) == 3:
                client.send_text(parts[1], parts[2])
            else:
                print("Usage: /msg <username> <text>")

        elif command.startswith("/file"):
            parts = command.split(" ", 2)
            if len(parts) == 3:
                client.send_file(parts[1], parts[2])
            else:
                print("Usage: /file <username> <path>")

        elif command.startswith("/block"):
            parts = command.split()
            if len(parts) == 2:
                client.block_user(parts[1])
            else:
                print("Usage: /block <username>")

        elif command.startswith("/create"):
            parts = command.split()
            if len(parts) == 2:
                client.create_group(parts[1])
            else:
                print("Usage: /create <group_name>")

        elif command.startswith("/add"):
            parts = command.split()
            if len(parts) == 3:
                client.add_user(parts[1], parts[2])
            else:
                print("Usage: /add <group_name> <username>")

        elif command.startswith("/gmsg"):
            parts = command.split(" ", 2)
            if len(parts) == 3:
                client.send_group_message(parts[1], parts[2])
            else:
                print("Usage: /gmsg <group_name> <text>")

        elif command.startswith("/join"):
            parts = command.split()
            if len(parts) == 2:
                client.join_group(parts[1])
            else:
                print("Usage: /join <group_name>")

        elif command.startswith("/leave"):
            parts = command.split()
            if len(parts) == 2:
                client.exit_group(parts[1])
            else:
                print("Usage: /leave <group_name>")

        elif command.startswith("/exit"):
            client.logout()

        else:
            print("Unknown command. Type /msg, /gmsg, /file, /block, /create, /add, /join, /leave, or /exit")