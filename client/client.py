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

    #Receives a message
    def receive_messages(self):
        while True:
            try:
                data = self.tcp_socket.recv(BUFFER_SIZE)

                if not data:
                    break

                header, body = data.decode().split(HEADER_BODY_SEPARATOR, 1)
                parsed = parse_tcp_header(header)

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
    def receiving_thread(self):
        thread = threading.Thread(target=self.receive_messages)
        thread.daemon = True      #Ensures the thread stops automatically when the main program exits
        thread.start()

    #Status updates using UDP
    def send_typing(self, receiver):
        msg = build_udp_message(TYPING, self.username, receiver)
        self.udp_socket.sendto(msg.encode(), (HOST, UDP_PORT))
    
