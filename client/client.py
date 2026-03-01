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
from file_transfer import send_file, receive_file

class ClientHandler:

    def __init__(self):
        self.username = None
        self.tcp_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

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
    def login(self, username):
        self.username = username
        msg = build_tcp_message(LOGIN, username, "SERVER")
        self.tcp_socket.sendall(msg.encode())
    
    #Sends a message
    def send_text(self, receiver, text):
        msg = build_tcp_message(TEXT, self.username, receiver, text)
        self.tcp_socket.sendall(msg.encode())

    #Saves any file
    def save_file(self, header_fields, file_bytes):
        os.makedirs(MEDIA_DIR, exist_ok=True)

        filename = header_fields.get("FILENAME", "received_file")
        filepath = os.path.join(MEDIA_DIR, filename)

        with open(filepath, "wb") as f:
            f.write(file_bytes)

        print(f"[FILE RECEIVED] Saved to {filepath}")

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
                    size = int(parsed.get(FIELD_SIZE, 0))

                    if len(buffer) < size:
                        buffer = header_part + HEADER_BODY_SEPARATOR.encode() + buffer
                        break

                    body = buffer[:size]
                    buffer = buffer[size:]

                    if msg_type in (IMAGE, VIDEO_FILE, AUDIO_FILE, DOCUMENT):
                        self.save_file(parsed, body)
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
    
