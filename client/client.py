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
    HEADER_BODY_SEPARATOR
)
from utils.message import (
    build_tcp_message, parse_tcp_header,
    build_udp_message, parse_udp_message, get_timestamp
)
from file_transfer import send_file, receive_file

class ClientHandler:

    def __init__(self):
        self.username = None
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        self.keep_running = True

        #P2P sever socket(for direct file transferes)
        self.p2p_server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.p2p_server_socket.bind(("0.0.0.0", 0))
        self.p2p_server_socket.listen(5)
        self.p2p_port = self.p2p_server_socket.getsockname()[1]

    #Connects to the server using TCP
    def connect(self):
        try:
            self.tcp_socket.connect((HOST, TCP_PORT))
            print("=== SEVER HANDSHAKE COMPLETE ===")
            print(f"Connected to server at {HOST}:{TCP_PORT}")
            print("Communication channnel open.")
        except Exception as e:
            print("=== CONNECTION FAILED ===")
            print("Unable to establish connection to server.")
            print("Please verify server availability.")
    
    #Logs in the user into the ChatApp
    def login(self, username, password):
        self.username = username
        msg = build_tcp_message(LOGIN, username, "SERVER", f"password: {password}")
        self.tcp_socket.sendall(msg.encode())

    #Logs out a user
    def logout(self):
        msg = build_tcp_message(LOGOUT, self.username, "SERVER")
        self.tcp_socket.sendall(msg.encode())
        self.keep_running = False
        self.tcp_socket.close()
        self.udp_socket.close()
        self.p2p_server_socket.close()

    #File transfer
    def send_file(self, receiver, filepath):
        send_file(self.tcp_socket, self.username, receiver, filepath)
    
    #Sends a message
    def send_text(self, receiver, text):
        msg = build_tcp_message(TEXT, self.username, receiver, text)
        self.tcp_socket.sendall(msg.encode())

    def create_group(self, group_name):
        msg = build_tcp_message(CREATE_GROUP, self.username, group_name)
        self.tcp_socket.sendall(msg.encode())

    def join_group(self, group_name):
        msg = build_tcp_message(JOIN_GROUP, self.username, group_name)
        self.tcp_socket.sendall(msg.encode())

    def add_user(self, group_name, user_to_add):
        msg = build_tcp_message(ADD_USER, self.username, group_name, user_to_add)
        self.tcp_socket.sendall(msg.encode())

    def remove_user(self, group_name, user_to_remove):
        msg = build_tcp_message(REMOVE_USER, self.username, group_name, user_to_remove)
        self.tcp_socket.sendall(msg.encode())

    def exit_group(self, group_name):
        msg = build_tcp_message(EXIT_GROUP, self.username, group_name)
        self.tcp_socket.sendall(msg.encode())

    def block_user(self, target_user):
        msg = build_tcp_message(BLOCK_USER, self.username, target_user)
        self.tcp_socket.sendall(msg.encode())

    #Receives a message
    def receive_messages(self):
        buffer = b""

        while True:
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

                    if msg_type in (IMAGE, VIDEO_FILE, AUDIO_FILE, DOCUMENT):
                        receive_file(self.tcp_socket, parsed)
                    else:
                        size = int(parsed.get(FIELD_SIZE, 0))
                        body_bytes = buffer[:size]
                        buffer = buffer[size:]
                        body = body_bytes.decode()

                        if msg_type == ACK:
                            print(f"[ACK] {parsed['FROM']} confirmed receipt.")
                        elif msg_type == ERROR:
                            print(f"[ERROR] {parsed['FROM']}: {body}")
                        elif msg_type == MESSAGE_FAILED:
                            print(f"[FAILED] Message to {parsed['TO']} could not be delivered.")
                        else:
                            print(f"\n┌─[{parsed['FROM']}] @ {parsed['TIMESTAMP']}")
                            print(f"| {body}")
                            print("└" + "─" * (len(str(body))+2))

            except Exception as e:
                error_msg = str(e)
                print(f"\n┌─[ERROR] NETWORK EXCEPTION")
                print(f"│ {error_msg}")
                print("└" + "─"*len(error_msg) + "\n")
                break

    def receive_udp(self):
        while self.keep_running:
            try:
                data, _ = self.udp_socket.recvfrom(BUFFER_SIZE)
                parsed = parse_udp_message(data.decode())

                if parsed:
                    print(f"\n[{parsed['TYPE']}] from {parsed['FROM']}")
            except:
                break
    
    #Listens for incoming messages from the server using threading
    def tcp_thread(self):
        thread = threading.Thread(target=self.receive_messages)
        thread.daemon = True      #Ensures the thread stops automatically when the main program exits
        thread.start()

    def udp_thread(self):
        thread = threading.Thread(target=self.receive_udp)
        thread.daemon = True
        thread.start()

    #Status updates using UDP
    def send_typing(self, receiver):
        msg = build_udp_message(TYPING, self.username, receiver)
        self.udp_socket.sendto(msg.encode(), (HOST, UDP_PORT))

    def send_keep_alive(self):
        while self.keep_running:
            try:
                msg = build_udp_message(KEEP_ALIVE, self.username, "SERVER")
                self.udp_socket.sendto(msg.encode(), (HOST, UDP_PORT))
                time.sleep(30)  # every 30 seconds
            except:
                break

    def keep_alive_thread(self):
        thread = threading.Thread(target=self.send_keep_alive)
        thread.daemon = True
        thread.start()

    