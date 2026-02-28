# A program that handles sending and receiving binary files over TCP.
# Author: MADZIBANDILA CHARMAIN
# Date: 28 February 2026

import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import (
    MEDIA_DIR, IMAGE, VIDEO_FILE, AUDIO_FILE, DOCUMENT,
    FIELD_TYPE, FIELD_FROM, FIELD_TO, FIELD_SIZE,
    HEADER_BODY_SEPARATOR
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
