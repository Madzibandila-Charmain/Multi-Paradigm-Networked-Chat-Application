# A program that handles sending and receiving binary files over TCP.
# Author: MADZIBANDILA CHARMAIN
# Date: 28 February 2026

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import (
    MEDIA_DIR, IMAGE, VIDEO_FILE, AUDIO_FILE, DOCUMENT,
    FIELD_TYPE, FIELD_FROM, FIELD_TO, FIELD_SIZE,
    HEADER_BODY_SEPARATOR, HEADER_FIELD_SEPARATOR, FIELD_TIMESTAMP
)
from utils.message import get_timestamp

# File type detection
IMAGE_EXTENSIONS    = {".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"}
VIDEO_EXTENSIONS    = {".mp4", ".avi", ".mov", ".mkv", ".wmv"}
AUDIO_EXTENSIONS    = {".mp3", ".wav", ".ogg", ".m4a", ".aac"}
DOCUMENT_EXTENSIONS = {".pdf", ".docx", ".doc", ".xlsx", ".xls", ".txt", ".pptx"}

def detect_file_type(filename):
    _, ext = os.path.splitext(filename.lower())

    if ext in IMAGE_EXTENSIONS:
        return IMAGE
    elif ext in VIDEO_EXTENSIONS:
        return VIDEO_FILE
    elif ext in AUDIO_EXTENSIONS:
        return AUDIO_FILE
    elif ext in DOCUMENT_EXTENSIONS:
        return DOCUMENT
    else:
        return None
    
#Sends file using TCP
def send_file(tcp_socket, sender, receiver, filepath):
    if not os.path.exists(filepath):
        print("[ERROR] File does not exist.")
        return
    
    msg_type = detect_file_type(filepath)

    if not msg_type:
        print("[ERROR] Unsupported file type.")
        return
    
    #Reads file as binary
    with open(filepath, "rb") as f:
        file_data = f.read()

    size = len(file_data)
    filename = os.path.basename(filepath)

    #Builds header manually for binary safety
    header = (
        f"{FIELD_TYPE}: {msg_type}{HEADER_FIELD_SEPARATOR}"
        f"{FIELD_FROM}: {sender}{HEADER_FIELD_SEPARATOR}"
        f"{FIELD_TO}: {receiver}{HEADER_FIELD_SEPARATOR}"
        f"{FIELD_TIMESTAMP}: {get_timestamp()}{HEADER_FIELD_SEPARATOR}"
        f"{FIELD_SIZE}: {size}{HEADER_FIELD_SEPARATOR}"
        f"FILENAME: {filename}"
    )

    message = header + HEADER_BODY_SEPARATOR

    # Send header first
    tcp_socket.sendall(message.encode())

    # Then send binary body
    tcp_socket.sendall(file_data)

    print(f"[FILE SENT] {os.path.basename(filepath)} ({size} bytes)")

#Receives the file
def receive_file(header_fields, file_bytes):

    # Use original filename if available, otherwise create one with timestamp
    if 'FILENAME' in header_fields:
        filename = header_fields['FILENAME']
    else:
        # Fallback: use timestamp + default extension
        timestamp = header_fields['TIMESTAMP'].replace(':', '-')
        msg_type = header_fields['TYPE']
        # Use first extension from the type sets as default
        default_ext = {
            IMAGE: ".png",
            VIDEO_FILE: ".mp4",
            AUDIO_FILE: ".mp3",
            DOCUMENT: ".pdf"
        }.get(msg_type, ".bin")
        filename = f"{msg_type}_{timestamp}{default_ext}"
    
    os.makedirs(MEDIA_DIR, exist_ok=True) #Ensures the directory exists

    filepath = os.path.join(MEDIA_DIR, filename)

    with open(filepath, "wb") as f:
        f.write(file_bytes)

    print(f"[FILE RECEIVED] Saved to {filepath}")