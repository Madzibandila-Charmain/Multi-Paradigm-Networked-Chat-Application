# CSC3002F - Protocol message builder and parser
# Used by both server and client to construct and decode messages.
# All message construction is centralised here so the format never drifts
# between endpoints - both sides use the exact same functions.

import os
import sys
from datetime import datetime

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import (
    FIELD_TYPE, FIELD_FROM, FIELD_TO, FIELD_TIMESTAMP, FIELD_SIZE,
    HEADER_BODY_SEPARATOR, HEADER_FIELD_SEPARATOR
)


def get_timestamp():
    """Returns current time formatted as ISO 8601 string."""
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def build_tcp_message(msg_type, sender, receiver, body=""):
    """
    Constructs a complete TCP protocol message as a string.

    Format:
        TYPE: <type>\r\n
        FROM: <sender>\r\n
        TO:   <receiver>\r\n
        TIMESTAMP: <ts>\r\n
        SIZE: <body_byte_length>\r\n\r\n
        <body>

    SIZE is measured in UTF-8 bytes so the receiver knows exactly how many
    bytes to read after the separator, regardless of multi-byte characters.
    """
    if isinstance(body, bytes):
        body = body.decode("utf-8", errors="replace")

    body_bytes = body.encode("utf-8")
    size = len(body_bytes)

    header = (
        f"{FIELD_TYPE}: {msg_type}{HEADER_FIELD_SEPARATOR}"
        f"{FIELD_FROM}: {sender}{HEADER_FIELD_SEPARATOR}"
        f"{FIELD_TO}: {receiver}{HEADER_FIELD_SEPARATOR}"
        f"{FIELD_TIMESTAMP}: {get_timestamp()}{HEADER_FIELD_SEPARATOR}"
        f"{FIELD_SIZE}: {size}"
    )
    return header + HEADER_BODY_SEPARATOR + body


def parse_tcp_header(header_text):
    """
    Parses a raw header string into a dict of field → value pairs.
    Returns None if the TYPE field is missing (i.e. the message is malformed).

    Each line in the header is expected to be "KEY: VALUE".
    """
    fields = {}
    for line in header_text.strip().split(HEADER_FIELD_SEPARATOR):
        if ": " in line:
            key, value = line.split(": ", 1)
            fields[key.strip()] = value.strip()

    return fields if FIELD_TYPE in fields else None


def build_udp_message(msg_type, sender, receiver):
    """
    Constructs a UDP status message as a string.

    UDP messages carry no body and therefore no SIZE field.
    Each datagram is a self-contained single update - there is no sequence
    number because lost packets are never retransmitted.

    Format:
        TYPE: <type>\r\n
        FROM: <sender>\r\n
        TO:   <receiver>\r\n
        TIMESTAMP: <ts>
    """
    return (
        f"{FIELD_TYPE}: {msg_type}{HEADER_FIELD_SEPARATOR}"
        f"{FIELD_FROM}: {sender}{HEADER_FIELD_SEPARATOR}"
        f"{FIELD_TO}: {receiver}{HEADER_FIELD_SEPARATOR}"
        f"{FIELD_TIMESTAMP}: {get_timestamp()}"
    )


def parse_udp_message(raw_message):
    """
    Parses a raw UDP datagram string.
    Reuses parse_tcp_header since the field format is identical -
    only the set of expected fields differs.
    """
    return parse_tcp_header(raw_message)