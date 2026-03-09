# CSC3002F Assignment 1 — Multi-Paradigm Networked Chat Application
## Group Members
- MDZMU005 — Madzibandila Charmain
- RNWMUK001 — Ranwashe Mukovhe
- VZXKON001 — Vezi Konke

---

## Requirements
- Python 3.8 or higher
- No external libraries required — all modules used are part of the Python standard library

---

## How to Run

### Step 1 — Set up the database (run this once before starting the server)
```
python -m database.db_setup
```
This creates the `ChatApp.db` SQLite database and registers the five test users. You only need to run this once. If you want to reset the database at any point, delete `ChatApp.db` and run this command again.

### Step 2 — Start the server
```
python -m server.server
```
The server starts on `127.0.0.1:9000` (TCP) and `127.0.0.1:9001` (UDP relay). Keep this terminal open while the clients are running.

### Step 3 — Start a client (open a new terminal for each client)
```
python -m client.client
```
Run this in a separate terminal for each user. The application supports a minimum of 5 concurrent clients.

---

## Test Users
The following users are pre-registered after running `db_setup.py`:

| Username | Password     |
|----------|--------------|
| mukovhe  | password123  |
| charmain | password123  |
| konke    | password123  |
| yashil   | password123  |
| mumi     | password123  |

To add more users, open `database/db_setup.py` and add lines in the format:
```python
register_user("username", "password")
```
Then delete `ChatApp.db` and run `python -m database.db_setup` again.

---

## Available Commands (in the client)
```
/msg <user> <text>       — Send a private message to a user
/file <user> <path>      — Send a file to a user
/block <user>            — Block a user from messaging you
/create <group>          — Create a new group
/add <group> <user>      — Add a user to a group
/gmsg <group> <text>     — Send a message to all group members
/join <group>            — Join an existing group
/leave <group>           — Leave a group
/exit                    — Log out and quit
```

## Project Structure
```
Assignment 2/
├── README.md
├── constants.py
├── Assignment1_Stage2_Report.pdf
├── Demo.mp4
├── constants.py                — Shared configuration and message type constants
├── server/
│   ├── server.py               — Main TCP server
│   └── udp_relay.py            — UDP relay for status messages
├── client/
│   ├── client.py               — Client application
│   └── file_transfer.py        — Binary file send and receive
├── database/
│   ├── db_setup.py             — Database initialisation and test user registration
│   └── db_manager.py           — All database operations
└── utils/
    └── message.py              — Protocol message builder and parser
```

## Notes
- All clients must be run on the same machine as the server when using `127.0.0.1`
- To run across devices on the same WiFi network, update `HOST` in `constants.py` to the server machine's local IP address (find it with `ipconfig` on Windows or `hostname -I` on Linux)
- Received files are saved to the `received_files/` directory