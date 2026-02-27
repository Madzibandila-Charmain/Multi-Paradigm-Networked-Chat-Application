# CSC3002F - Multi-Paradigm Chat Application
# All database read/write functions
# The server calls these functions - it never accesses the database directly

import sqlite3
import hashlib
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import DB_NAME