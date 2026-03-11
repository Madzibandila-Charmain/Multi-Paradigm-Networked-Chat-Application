"""
CSC3002F Chat Application - GUI
used customtkinter
Run gui.py to view graphical interface
"""

import customtkinter as ctk
import tkinter as tk
from tkinter import filedialog, messagebox
import threading
import socket
import os
import sys
import time
from datetime import datetime

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# patch receive_messages so GUI can intercept incoming data
from client.client import ClientHandler
from constants import (
    ACK, ERROR, MESSAGE_FAILED, TEXT, IMAGE, VIDEO_FILE,
    AUDIO_FILE, DOCUMENT, USER_ONLINE, USER_OFFLINE, TYPING,
    FIELD_FROM, FIELD_TYPE
)
from utils.message import build_tcp_message, parse_tcp_header
from constants import HEADER_BODY_SEPARATOR, FIELD_SIZE

# Appearance
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")

DARK_BG      = "#0f1117"
PANEL_BG     = "#161b22"
SIDEBAR_BG   = "#0d1117"
INPUT_BG     = "#1c2128"
ACCENT       = "#2f81f7"
ACCENT_HOVER = "#388bfd"
SUCCESS      = "#3fb950"
WARNING      = "#d29922"
DANGER       = "#f85149"
TEXT_PRIMARY = "#e6edf3"
TEXT_MUTED   = "#7d8590"
BORDER       = "#30363d"
MSG_SENT_BG  = "#1f3d6e"
MSG_RECV_BG  = "#1c2128"
FONT_MAIN    = ("Courier New", 13)
FONT_SMALL   = ("Courier New", 11)
FONT_TITLE   = ("Courier New", 18, "bold")
FONT_MONO    = ("Courier New", 12)


#  Llogin window
class LoginWindow(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("CSC3002F Chat")
        self.geometry("420x520")
        self.resizable(False, False)
        self.configure(fg_color=DARK_BG)

        self.client = None
        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self.destroy)

    def _build_ui(self):
        # header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(pady=(48, 0), padx=40, fill="x")

        ctk.CTkLabel(
            header, text="◈ CSC3002F", font=("Courier New", 26, "bold"),
            text_color=ACCENT
        ).pack()
        ctk.CTkLabel(
            header, text="SECURE CHAT TERMINAL",
            font=("Courier New", 11), text_color=TEXT_MUTED
        ).pack(pady=(2, 0))

        # divider
        ctk.CTkFrame(self, height=1, fg_color=BORDER).pack(
            fill="x", padx=40, pady=24
        )

        # form
        form = ctk.CTkFrame(self, fg_color="transparent")
        form.pack(padx=40, fill="x")

        ctk.CTkLabel(form, text="USERNAME", font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(anchor="w")
        self.username_entry = ctk.CTkEntry(
            form, height=42, fg_color=INPUT_BG, border_color=BORDER,
            border_width=1, text_color=TEXT_PRIMARY, font=FONT_MONO,
            placeholder_text="enter username..."
        )
        self.username_entry.pack(fill="x", pady=(4, 16))

        ctk.CTkLabel(form, text="PASSWORD", font=FONT_SMALL,
                     text_color=TEXT_MUTED).pack(anchor="w")
        self.password_entry = ctk.CTkEntry(
            form, height=42, fg_color=INPUT_BG, border_color=BORDER,
            border_width=1, text_color=TEXT_PRIMARY, font=FONT_MONO,
            placeholder_text="enter password...", show="●"
        )
        self.password_entry.pack(fill="x", pady=(4, 0))
        self.password_entry.bind("<Return>", lambda e: self._do_login())

        #status label
        self.status_label = ctk.CTkLabel(
            form, text="", font=FONT_SMALL, text_color=TEXT_MUTED
        )
        self.status_label.pack(pady=(10, 0))

        # button for logging in
        self.login_btn = ctk.CTkButton(
            form, text="CONNECT →", height=44, font=("Courier New", 13, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._do_login
        )
        self.login_btn.pack(fill="x", pady=(20, 0))

        # footer
        ctk.CTkLabel(
            self, text="TCP:9000  UDP:9001  P2P:auto",
            font=("Courier New", 10), text_color=TEXT_MUTED
        ).pack(side="bottom", pady=16)

    def _set_status(self, msg, color=TEXT_MUTED):
        self.status_label.configure(text=msg, text_color=color)
        self.update_idletasks()

    def _do_login(self):
        username = self.username_entry.get().strip()
        password = self.password_entry.get().strip()

        if not username or not password:
            self._set_status("⚠ username and password required", WARNING)
            return

        self.login_btn.configure(state="disabled", text="connecting...")
        self._set_status("establishing connection...", TEXT_MUTED)

        def attempt():
            try:
                client = ClientHandler()
                client.connect()
                login_success = client.login(username, password)

                if login_success:
                    self.client = client
                    self.after(0, self._on_login_success)
                else:
                    self.after(0, lambda: self._on_login_fail("Login failed - invalid credentials"))
            except Exception as e:
                self.after(0, lambda: self._on_login_fail(str(e)))

        threading.Thread(target=attempt, daemon=True).start()

    def _on_login_success(self):
        self.withdraw()
        app = ChatApp(self.client)
        app.mainloop()
        self.destroy()

    def _on_login_fail(self, err):
        self._set_status(f"✗ {err}", DANGER)
        self.login_btn.configure(state="normal", text="CONNECT →")

#  Main chat app
class ChatApp(ctk.CTk):
    def __init__(self, client: ClientHandler):
        super().__init__()
        self.client = client
        self.username = client.username
        self.current_chat = None      # username or group name currently open
        self.online_users = set()
        self.chat_histories = {}      # {name: [(sender, text, timestamp), ...]}
        self.unread = {}              # {name: count}

        self.title(f"CSC3002F Chat  —  {self.username}")
        self.geometry("1100x720")
        self.minsize(900, 600)
        self.configure(fg_color=DARK_BG)

        self._build_ui()
        self._start_receive_thread()
        # Start only UDP, keep-alive, and P2P threads (NOT TCP - we handle that in GUI)
        self.client.udp_thread()
        self.client.keep_alive_thread()
        self.client.start_p2p_thread()

        self.protocol("WM_DELETE_WINDOW", self._on_close)

    # Ui
    def _build_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        self._build_sidebar()
        self._build_chat_panel()

    def _build_sidebar(self):
        sidebar = ctk.CTkFrame(
            self, width=240, fg_color=SIDEBAR_BG, corner_radius=0
        )
        sidebar.grid(row=0, column=0, sticky="nsew")
        sidebar.grid_propagate(False)
        sidebar.grid_rowconfigure(3, weight=1)

        # ── user badge ──
        badge = ctk.CTkFrame(sidebar, fg_color=PANEL_BG, corner_radius=0)
        badge.grid(row=0, column=0, sticky="ew", padx=0, pady=0)
        ctk.CTkLabel(
            badge, text="◈ CSC3002F", font=("Courier New", 14, "bold"),
            text_color=ACCENT
        ).pack(side="left", padx=14, pady=12)
        ctk.CTkLabel(
            badge, text=f"[{self.username}]",
            font=FONT_SMALL, text_color=SUCCESS
        ).pack(side="right", padx=14)

        #search
        search_frame = ctk.CTkFrame(sidebar, fg_color="transparent")
        search_frame.grid(row=1, column=0, sticky="ew", padx=10, pady=(10, 4))
        self.search_var = tk.StringVar()
        self.search_var.trace("w", self._filter_conversations)
        ctk.CTkEntry(
            search_frame, textvariable=self.search_var,
            placeholder_text="search...", height=32,
            fg_color=INPUT_BG, border_color=BORDER, border_width=1,
            text_color=TEXT_PRIMARY, font=FONT_SMALL
        ).pack(fill="x")

        # ── section label ──
        ctk.CTkLabel(
            sidebar, text="CONVERSATIONS", font=("Courier New", 10),
            text_color=TEXT_MUTED
        ).grid(row=2, column=0, sticky="w", padx=14, pady=(8, 2))

        # conversation list
        self.conv_frame = ctk.CTkScrollableFrame(
            sidebar, fg_color="transparent", scrollbar_button_color=BORDER
        )
        self.conv_frame.grid(row=3, column=0, sticky="nsew", padx=0, pady=0)
        self.conv_buttons = {}   # {name: CTkButton}

        #bottom buttons
        bottom = ctk.CTkFrame(sidebar, fg_color=PANEL_BG, corner_radius=0)
        bottom.grid(row=4, column=0, sticky="ew")
        for text, cmd in [
            ("＋ New Chat", self._open_new_chat_dialog),
            ("⊞ Group", self._open_group_dialog),
            ("⊘ Block", self._open_block_dialog),
            ("⏻ Logout", self._on_close),
        ]:
            ctk.CTkButton(
                bottom, text=text, height=34, font=FONT_SMALL,
                fg_color="transparent", hover_color=INPUT_BG,
                text_color=TEXT_PRIMARY, anchor="w",
                command=cmd
            ).pack(fill="x", padx=6, pady=2)

        ctk.CTkFrame(bottom, height=8, fg_color="transparent").pack()

    def _build_chat_panel(self):
        panel = ctk.CTkFrame(self, fg_color=DARK_BG, corner_radius=0)
        panel.grid(row=0, column=1, sticky="nsew")
        panel.grid_rowconfigure(1, weight=1)
        panel.grid_columnconfigure(0, weight=1)

        #chat header
        self.chat_header = ctk.CTkFrame(
            panel, fg_color=PANEL_BG, height=52, corner_radius=0
        )
        self.chat_header.grid(row=0, column=0, sticky="ew")
        self.chat_header.grid_propagate(False)

        self.header_label = ctk.CTkLabel(
            self.chat_header, text="select a conversation",
            font=("Courier New", 14, "bold"), text_color=TEXT_MUTED
        )
        self.header_label.pack(side="left", padx=18, pady=14)

        self.status_dot = ctk.CTkLabel(
            self.chat_header, text="", font=FONT_SMALL, text_color=TEXT_MUTED
        )
        self.status_dot.pack(side="left")

        # file send button in header
        self.file_btn = ctk.CTkButton(
            self.chat_header, text="⊕ file", width=80, height=30,
            font=FONT_SMALL, fg_color="transparent",
            border_color=BORDER, border_width=1,
            hover_color=INPUT_BG, text_color=TEXT_MUTED,
            command=self._send_file
        )
        self.file_btn.pack(side="right", padx=12)

        # message area
        self.msg_area = ctk.CTkScrollableFrame(
            panel, fg_color=DARK_BG, scrollbar_button_color=BORDER
        )
        self.msg_area.grid(row=1, column=0, sticky="nsew", padx=0, pady=0)

        # typing indicator
        self.typing_label = ctk.CTkLabel(
            panel, text="", font=("Courier New", 11, "italic"),
            text_color=TEXT_MUTED
        )
        self.typing_label.grid(row=2, column=0, sticky="w", padx=18)

        # ── input row ──
        input_row = ctk.CTkFrame(panel, fg_color=PANEL_BG, corner_radius=0)
        input_row.grid(row=3, column=0, sticky="ew")
        input_row.grid_columnconfigure(0, weight=1)

        self.msg_input = ctk.CTkEntry(
            input_row, placeholder_text="type a message...",
            height=46, fg_color=INPUT_BG, border_color=BORDER,
            border_width=1, text_color=TEXT_PRIMARY, font=FONT_MONO
        )
        self.msg_input.grid(row=0, column=0, padx=(12, 6), pady=10, sticky="ew")
        self.msg_input.bind("<Return>", lambda e: self._send_message())
        self.msg_input.bind("<KeyPress>", self._on_typing)

        ctk.CTkButton(
            input_row, text="SEND", width=80, height=46,
            font=("Courier New", 12, "bold"),
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=self._send_message
        ).grid(row=0, column=1, padx=(0, 12), pady=10)

        self._show_placeholder()

    def _show_placeholder(self):
        for w in self.msg_area.winfo_children():
            w.destroy()
        ctk.CTkLabel(
            self.msg_area,
            text="◈\n\nselect a conversation\nor start a new one",
            font=("Courier New", 14), text_color=TEXT_MUTED,
            justify="center"
        ).pack(expand=True, pady=120)

    #convo list
    def _add_or_update_conversation(self, name):
        if name in self.conv_buttons:
            self._refresh_conv_button(name)
            return

        btn = ctk.CTkButton(
            self.conv_frame,
            text=self._conv_label(name),
            anchor="w", font=FONT_SMALL,
            height=44, corner_radius=6,
            fg_color="transparent", hover_color=INPUT_BG,
            text_color=TEXT_PRIMARY,
            command=lambda n=name: self._open_chat(n)
        )
        btn.pack(fill="x", padx=6, pady=2)
        self.conv_buttons[name] = btn

    def _conv_label(self, name):
        unread = self.unread.get(name, 0)
        suffix = f"  [{unread}]" if unread > 0 else ""
        online = "● " if name in self.online_users else "○ "
        return f"{online}{name}{suffix}"

    def _refresh_conv_button(self, name):
        if name in self.conv_buttons:
            highlight = name == self.current_chat
            self.conv_buttons[name].configure(
                text=self._conv_label(name),
                fg_color=INPUT_BG if highlight else "transparent"
            )

    def _filter_conversations(self, *_):
        query = self.search_var.get().lower()
        for name, btn in self.conv_buttons.items():
            if query in name.lower():
                btn.pack(fill="x", padx=6, pady=2)
            else:
                btn.pack_forget()

    # oppen chat
    def _open_chat(self, name):
        self.current_chat = name
        self.unread[name] = 0

        # update header
        self.header_label.configure(text=name, text_color=TEXT_PRIMARY)
        online = name in self.online_users
        self.status_dot.configure(
            text="● online" if online else "○ offline",
            text_color=SUCCESS if online else TEXT_MUTED
        )

        # highlight selected
        for n in self.conv_buttons:
            self._refresh_conv_button(n)

        # render messages
        self._render_messages(name)

    def _render_messages(self, name):
        for w in self.msg_area.winfo_children():
            w.destroy()

        history = self.chat_histories.get(name, [])
        if not history:
            ctk.CTkLabel(
                self.msg_area, text="no messages yet",
                font=FONT_SMALL, text_color=TEXT_MUTED
            ).pack(pady=40)
            return

        for sender, text, ts in history:
            self._render_bubble(sender, text, ts)

        # scroll to bottom
        self.after(50, lambda: self.msg_area._parent_canvas.yview_moveto(1.0))

    def _render_bubble(self, sender, text, ts):
        is_me = sender == self.username
        outer = ctk.CTkFrame(self.msg_area, fg_color="transparent")
        outer.pack(fill="x", padx=12, pady=3)

        bubble = ctk.CTkFrame(
            outer,
            fg_color=MSG_SENT_BG if is_me else MSG_RECV_BG,
            corner_radius=10
        )
        bubble.pack(side="right" if is_me else "left")

        if not is_me:
            ctk.CTkLabel(
                bubble, text=sender, font=("Courier New", 10, "bold"),
                text_color=ACCENT
            ).pack(anchor="w", padx=10, pady=(6, 0))

        ctk.CTkLabel(
            bubble, text=text, font=FONT_MONO,
            text_color=TEXT_PRIMARY, wraplength=420, justify="left"
        ).pack(padx=10, pady=(2, 2))

        ctk.CTkLabel(
            bubble, text=ts, font=("Courier New", 9),
            text_color=TEXT_MUTED
        ).pack(anchor="e", padx=10, pady=(0, 6))

    def _append_message(self, chat_name, sender, text, ts=None):
        ts = ts or datetime.now().strftime("%H:%M")
        if chat_name not in self.chat_histories:
            self.chat_histories[chat_name] = []
        self.chat_histories[chat_name].append((sender, text, ts))

        if chat_name == self.current_chat:
            self._render_bubble(sender, text, ts)
            self.after(50, lambda: self.msg_area._parent_canvas.yview_moveto(1.0))
        else:
            self.unread[chat_name] = self.unread.get(chat_name, 0) + 1
            self._add_or_update_conversation(chat_name)

    # send
    def _send_message(self):
        if not self.current_chat:
            messagebox.showinfo("No chat", "Open a conversation first.")
            return
        text = self.msg_input.get().strip()
        if not text:
            return

        # check if it's a group (group names stored with grp prefix logic — just use name)
        if self.current_chat.startswith("grp:"):
            group = self.current_chat[4:]
            self.client.send_group_message(group, text)
        else:
            self.client.send_text(self.current_chat, text)

        ts = datetime.now().strftime("%H:%M")
        self._append_message(self.current_chat, self.username, text, ts)
        self.msg_input.delete(0, "end")

    def _send_file(self):
        if not self.current_chat:
            messagebox.showinfo("File send", "Open a conversation to send files.")
            return
        if self.current_chat.startswith("grp:"):
            messagebox.showinfo("File send", "File sending is only available for direct chats.")
            return
        path = filedialog.askopenfilename(
            title="Select file",
            filetypes=[
                ("Images", "*.jpg *.jpeg *.png *.gif *.bmp *.webp"),
                ("Videos", "*.mp4 *.avi *.mov *.mkv"),
                ("Audio",  "*.mp3 *.wav *.ogg *.m4a"),
                ("Documents", "*.pdf *.docx *.doc *.xlsx *.txt *.pptx"),
                ("All files", "*.*"),
            ]
        )
        if not path:
            return
        threading.Thread(
            target=self.client.send_file,
            args=(self.current_chat, path),
            daemon=True
        ).start()
        fname = os.path.basename(path)
        self._append_message(
            self.current_chat, self.username, f"📎 {fname}", datetime.now().strftime("%H:%M")
        )

    def _on_typing(self, event):
        if self.current_chat and not self.current_chat.startswith("grp:"):
            try:
                self.client.send_typing(self.current_chat)
            except Exception:
                pass

    # REceive thread
    def _start_receive_thread(self):
        """Custom receive loop that feeds messages into the GUI."""
        from constants import BUFFER_SIZE, HEADER_BODY_SEPARATOR

        def loop():
            buffer = b""
            sep = HEADER_BODY_SEPARATOR.encode()

            while self.client.keep_running:
                try:
                    data = self.client.tcp_socket.recv(BUFFER_SIZE)
                    if not data:
                        break
                    buffer += data

                    while sep in buffer:
                        header_part, buffer = buffer.split(sep, 1)
                        header = parse_tcp_header(header_part.decode())
                        if not header:
                            continue

                        msg_type = header.get(FIELD_TYPE, "")
                        size = int(header.get(FIELD_SIZE, 0))

                        if len(buffer) < size:
                            buffer = header_part + sep + buffer
                            break

                        body_bytes = buffer[:size]
                        buffer = buffer[size:]
                        body = body_bytes.decode(errors="ignore")

                        self.after(0, lambda h=header, b=body, mb=body_bytes, mt=msg_type:
                                   self._handle_incoming(h, b, mb, mt))

                except socket.error as e:
                    if self.client.keep_running:
                        print(f"[GUI RECV SOCKET ERROR] {e}")
                    break
                except Exception as e:
                    if self.client.keep_running:
                        print(f"[GUI RECV ERROR] {e}")
                    break

        threading.Thread(target=loop, daemon=True).start()

    def _handle_incoming(self, header, body, body_bytes, msg_type):
        sender = header.get(FIELD_FROM, "?")
        ts = datetime.now().strftime("%H:%M")

        if msg_type == ACK:
            # show small status feedbackdon't pollute chat
            self._flash_status(f"✓ {body}")

        elif msg_type == ERROR:
            self._flash_status(f"✗ {body}", DANGER)

        elif msg_type == MESSAGE_FAILED:
            self._flash_status(f"⚠ {body}", WARNING)

        elif msg_type == TEXT:
            # Check if it's a group message (has [groupname] prefix from server)
            import re
            group_match = re.match(r'^\[(.+?)\]\s*(.*)', body)
            if group_match:
                # Group message
                group_name = group_match.group(1)
                message_text = group_match.group(2)
                chat = f"grp:{group_name}"
                self._add_or_update_conversation(chat)
                self._append_message(chat, sender, message_text, ts)
            else:
                # Direct message
                chat = sender
                self._add_or_update_conversation(chat)
                self._append_message(chat, sender, body, ts)

        elif msg_type in (IMAGE, VIDEO_FILE, AUDIO_FILE, DOCUMENT):
            from client.file_transfer import receive_file
            receive_file(header, body_bytes)
            fname = header.get("FILENAME", "file")
            self._add_or_update_conversation(sender)
            self._append_message(sender, sender, f"📎 received: {fname}", ts)

        elif msg_type == USER_ONLINE:
            self.online_users.add(sender)
            self._add_or_update_conversation(sender)
            self._refresh_conv_button(sender)
            if sender == self.current_chat:
                self.status_dot.configure(text="● online", text_color=SUCCESS)

        elif msg_type == USER_OFFLINE:
            self.online_users.discard(sender)
            self._refresh_conv_button(sender)
            if sender == self.current_chat:
                self.status_dot.configure(text="○ offline", text_color=TEXT_MUTED)

        elif msg_type == TYPING:
            self.typing_label.configure(text=f"{sender} is typing...")
            self.after(2000, lambda: self.typing_label.configure(text=""))

        elif msg_type == "P2P_SIGNAL":
            # Server has approved P2P transfer, extract peer info and initiate send
            try:
                lines = body.split("\n")
                peer_ip       = lines[0].split(": ", 1)[1]
                peer_port     = int(lines[1].split(": ", 1)[1])
                peer_username = lines[2].split(": ", 1)[1]
                filename      = lines[3].split(": ", 1)[1]
                filepath      = lines[4].split(": ", 1)[1]

                # Start P2P file transfer in background thread
                threading.Thread(
                    target=self.client._do_p2p_send,
                    args=(peer_ip, peer_port, peer_username, filename, filepath),
                    daemon=True
                ).start()
                self._flash_status(f"📤 Sending {filename} to {peer_username}...")
            except Exception as e:
                self._flash_status(f"✗ P2P transfer failed: {e}", DANGER)

        elif msg_type == "P2P_INCOMING":
            # Peer is about to send us a file via P2P
            try:
                lines = body.split("\n")
                peer_ip   = lines[0].split(": ", 1)[1]
                sender_user = lines[1].split(": ", 1)[1]
                filename  = lines[2].split(": ", 1)[1]
                filesize  = lines[3].split(": ", 1)[1]
                self._flash_status(f"📥 Receiving {filename} from {sender_user}...")
            except Exception as e:
                self._flash_status(f"✗ Failed to parse P2P incoming: {e}", DANGER)

        elif msg_type == "P2P_DENIED":
            self._flash_status(f"✗ {body}", DANGER)

    def _flash_status(self, msg, color=SUCCESS):
        self.typing_label.configure(text=msg, text_color=color)
        self.after(2500, lambda: self.typing_label.configure(text="", text_color=TEXT_MUTED))

    # dialogs
    def _open_new_chat_dialog(self):
        dialog = ctk.CTkInputDialog(
            text="Enter username to chat with:",
            title="New Chat"
        )
        name = dialog.get_input()
        if name and name.strip():
            name = name.strip()
            self._add_or_update_conversation(name)
            self._open_chat(name)

    def _open_group_dialog(self):
        win = ctk.CTkToplevel(self)
        win.title("Group Management")
        win.geometry("380x480")
        win.configure(fg_color=DARK_BG)
        win.grab_set()

        ctk.CTkLabel(win, text="GROUP MANAGEMENT",
                     font=("Courier New", 14, "bold"), text_color=ACCENT).pack(pady=(24, 16))

        sections = [
            ("Create Group", "group name", self._do_create_group),
            ("Join Group",   "group name", self._do_join_group),
            ("Leave Group",  "group name", self._do_leave_group),
        ]
        entries = {}
        for label, ph, cmd in sections:
            frame = ctk.CTkFrame(win, fg_color=PANEL_BG, corner_radius=8)
            frame.pack(fill="x", padx=20, pady=6)
            ctk.CTkLabel(frame, text=label, font=FONT_SMALL,
                         text_color=TEXT_MUTED).pack(anchor="w", padx=12, pady=(10, 2))
            e = ctk.CTkEntry(frame, placeholder_text=ph, fg_color=INPUT_BG,
                             border_color=BORDER, text_color=TEXT_PRIMARY, font=FONT_MONO)
            e.pack(fill="x", padx=12, pady=(0, 6))
            entries[label] = e
            ctk.CTkButton(
                frame, text=label, height=32, font=FONT_SMALL,
                fg_color=ACCENT, hover_color=ACCENT_HOVER,
                command=lambda c=cmd, en=e: (c(en.get().strip()), win.destroy())
            ).pack(fill="x", padx=12, pady=(0, 10))

        # Add user to group
        add_frame = ctk.CTkFrame(win, fg_color=PANEL_BG, corner_radius=8)
        add_frame.pack(fill="x", padx=20, pady=6)
        ctk.CTkLabel(add_frame, text="Add User to Group",
                     font=FONT_SMALL, text_color=TEXT_MUTED).pack(anchor="w", padx=12, pady=(10, 2))
        grp_e = ctk.CTkEntry(add_frame, placeholder_text="group name",
                              fg_color=INPUT_BG, border_color=BORDER,
                              text_color=TEXT_PRIMARY, font=FONT_MONO)
        grp_e.pack(fill="x", padx=12, pady=(0, 4))
        usr_e = ctk.CTkEntry(add_frame, placeholder_text="username to add",
                              fg_color=INPUT_BG, border_color=BORDER,
                              text_color=TEXT_PRIMARY, font=FONT_MONO)
        usr_e.pack(fill="x", padx=12, pady=(0, 6))
        ctk.CTkButton(
            add_frame, text="Add User", height=32, font=FONT_SMALL,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
            command=lambda: (self.client.add_user(grp_e.get().strip(), usr_e.get().strip()), win.destroy())
        ).pack(fill="x", padx=12, pady=(0, 10))

    def _do_create_group(self, name):
        if name:
            self.client.create_group(name)
            conv_key = f"grp:{name}"
            self.chat_histories[conv_key] = []
            self._add_or_update_conversation(conv_key)

    def _do_join_group(self, name):
        if name:
            self.client.join_group(name)
            conv_key = f"grp:{name}"
            self.chat_histories[conv_key] = []
            self._add_or_update_conversation(conv_key)

    def _do_leave_group(self, name):
        if name:
            self.client.exit_group(name)

    def _open_block_dialog(self):
        dialog = ctk.CTkInputDialog(
            text="Enter username to block:",
            title="Block User"
        )
        name = dialog.get_input()
        if name and name.strip():
            self.client.block_user(name.strip())
            self._flash_status(f"✓ {name.strip()} blocked", WARNING)

    # close
    def _on_close(self):
        try:
            self.client.logout()
        except (socket.error, Exception):
            pass
        self.destroy()


if __name__ == "__main__":
    app = LoginWindow()
    app.mainloop()