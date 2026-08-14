import sqlite3
import json
import uuid
from pathlib import Path
from typing import List, Dict, Any, Optional

DB_PATH = Path("data/chat_history.db")

class ChatHistoryDB:
    def __init__(self, db_path: Path = DB_PATH):
        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def _init_db(self):
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS sessions (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS messages (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    session_id TEXT NOT NULL,
                    role TEXT NOT NULL,
                    content TEXT NOT NULL,
                    metadata TEXT DEFAULT '{}',
                    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (session_id) REFERENCES sessions (id) ON DELETE CASCADE
                )
            """)
            conn.commit()

    def create_session(self, title: str = "New chat") -> Dict[str, Any]:
        session_id = str(uuid.uuid4())
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "INSERT INTO sessions (id, title) VALUES (?, ?)",
                (session_id, title)
            )
            conn.commit()
        return self.get_session(session_id)

    def list_sessions(self) -> List[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT s.id, s.title, s.created_at, s.updated_at,
                       COUNT(m.id) as message_count
                FROM sessions s
                LEFT JOIN messages m ON s.id = m.session_id
                GROUP BY s.id
                ORDER BY s.updated_at DESC
            """)
            rows = cursor.fetchall()
            return [dict(row) for row in rows]

    def get_session(self, session_id: str) -> Optional[Dict[str, Any]]:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            session_row = cursor.fetchone()
            if not session_row:
                return None

            cursor.execute("""
                SELECT id, role, content, metadata, timestamp
                FROM messages
                WHERE session_id = ?
                ORDER BY id ASC
            """, (session_id,))
            msg_rows = cursor.fetchall()

            messages = []
            for m in msg_rows:
                msg_dict = dict(m)
                try:
                    msg_dict["metadata"] = json.loads(msg_dict["metadata"])
                except Exception:
                    msg_dict["metadata"] = {}
                messages.append(msg_dict)

            res = dict(session_row)
            res["messages"] = messages
            return res

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        meta_str = json.dumps(metadata or {})
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO messages (session_id, role, content, metadata)
                VALUES (?, ?, ?, ?)
            """, (session_id, role, content, meta_str))
            
            # If user message and session title is still default, update title
            if role == "user":
                cursor.execute("SELECT title FROM sessions WHERE id = ?", (session_id,))
                row = cursor.fetchone()
                if row and row["title"] == "New chat":
                    new_title = content[:35] + ("..." if len(content) > 35 else "")
                    cursor.execute(
                        "UPDATE sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (new_title, session_id)
                    )
                else:
                    cursor.execute(
                        "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                        (session_id,)
                    )
            else:
                cursor.execute(
                    "UPDATE sessions SET updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                    (session_id,)
                )
            conn.commit()

        return self.get_session(session_id)

    def rename_session(self, session_id: str, new_title: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "UPDATE sessions SET title = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (new_title, session_id)
            )
            conn.commit()
            return cursor.rowcount > 0

    def delete_session(self, session_id: str) -> bool:
        with self._get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM messages WHERE session_id = ?", (session_id,))
            cursor.execute("DELETE FROM sessions WHERE id = ?", (session_id,))
            conn.commit()
            return cursor.rowcount > 0
