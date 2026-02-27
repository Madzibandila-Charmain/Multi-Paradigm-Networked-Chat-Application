# CSC3002F - Multi-Paradigm Chat Application
# Helper functions for building and parsing protocol messages
# Both the server and client import from this file

import datetime
from constants import (
    FIELD_TYPE, FIELD_FROM, FIELD_TO, FIELD_TIMESTAMP, FIELD_SIZE,
    HEADER_BODY_SEPARATOR, HEADER_FIELD_SEPARATOR
)


def get_timestamp():
    """
    Returns the current date and time as a formatted string.
    Format: YYYY-MM-DDTHH:MM:SS
    Used in every message header to record when the message was sent.
    """
    return datetime.datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def build_tcp_message(msg_type, sender, receiver, body=""):
    """
    Builds a complete TCP message ready to be sent over a socket.

    Parameters:
        msg_type  - the type of message e.g. TEXT, LOGIN, ACK
        sender    - the username of the user sending the message
        receiver  - the username of the intended recipient
        body      - the message content, empty string by default

    Returns:
        A string containing the full header and body separated by HEADER_BODY_SEPARATOR.
        The SIZE field in the header reflects the byte length of the body.
    """
    body_bytes = body.encode("utf-8") if isinstance(body, str) else body
    size = len(body_bytes)

    header = (
        f"{FIELD_TYPE}: {msg_type}{HEADER_FIELD_SEPARATOR}"
        f"{FIELD_FROM}: {sender}{HEADER_FIELD_SEPARATOR}"
        f"{FIELD_TO}: {receiver}{HEADER_FIELD_SEPARATOR}"
        f"{FIELD_TIMESTAMP}: {get_timestamp()}{HEADER_FIELD_SEPARATOR}"
        f"{FIELD_SIZE}: {size}"
    )

    return header + HEADER_BODY_SEPARATOR + (body if isinstance(body, str) else "")


def parse_tcp_header(raw_header):
    """
    Parses a raw TCP header string into a dictionary.

    Parameters:
        raw_header - the header portion of a received TCP message as a string

    Returns:
        A dictionary with keys TYPE, FROM, TO, TIMESTAMP, SIZE.
        Returns None if the header is malformed or cannot be parsed.

    Example:
        Input:  "TYPE: TEXT\r\nFROM: mukovhe\r\nTO: charmain\r\nTIMESTAMP: ...\r\nSIZE: 5"
        Output: {"TYPE": "TEXT", "FROM": "mukovhe", "TO": "charmain", ...}
    """
    try:
        fields = {}
        for line in raw_header.strip().split(HEADER_FIELD_SEPARATOR):
            if ": " in line:
                key, value = line.split(": ", 1)
                fields[key.strip()] = value.strip()
        return fields
    except Exception as e:
        print(f"[ERROR] Failed to parse TCP header: {e}")
        return None


def build_udp_message(msg_type, sender, receiver):
    """
    Builds a UDP status update message ready to be sent via the server relay.

    UDP messages have no body - the header alone carries all the information.
    SIZE is not included since there is nothing to measure.
    Used for TYPING, USER_ONLINE, USER_OFFLINE and KEEP_ALIVE messages.

    Parameters:
        msg_type  - the type of status update e.g. TYPING, USER_ONLINE
        sender    - the username of the user sending the update
        receiver  - the username of the intended recipient

    Returns:
        A string containing the complete UDP message header.
    """
    return (
        f"{FIELD_TYPE}: {msg_type}{HEADER_FIELD_SEPARATOR}"
        f"{FIELD_FROM}: {sender}{HEADER_FIELD_SEPARATOR}"
        f"{FIELD_TO}: {receiver}{HEADER_FIELD_SEPARATOR}"
        f"{FIELD_TIMESTAMP}: {get_timestamp()}"
    )


def parse_udp_message(raw_message):
    """
    Parses a raw UDP message string into a dictionary.

    Parameters:
        raw_message - the full UDP message received as a string

    Returns:
        A dictionary with keys TYPE, FROM, TO, TIMESTAMP.
        Returns None if the message is malformed or cannot be parsed.
    """
    try:
        fields = {}
        for line in raw_message.strip().split(HEADER_FIELD_SEPARATOR):
            if ": " in line:
                key, value = line.split(": ", 1)
                fields[key.strip()] = value.strip()
        return fields
    except Exception as e:
        print(f"[ERROR] Failed to parse UDP message: {e}")
        return None