# CSC3002F - Multi-Paradigm Chat Application
# MUKOVHE - Database table creation
# This creates the SQLite database file and all the tables 
# The database is stored as a single file: ChatApp.db

import sqlite3
import os
import sys

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from constants import DB_NAME