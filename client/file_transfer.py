# CSC3002F - Multi-Paradigm Chat Application
# CHARMAIN - File sending and receiving
# Handles sending and receiving binary files over TCP.

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


