"""Validated in-memory snapshots sent by the optional native pipe transport."""

import copy
import json
import threading
import time

MAX_MESSAGE_BYTES = 65536
STALE_AFTER_SECONDS = 30


class NativeState:
    def __init__(self):
        self._lock = threading.Lock()
        self._session = None
        self._sequence = -1
        self._data = None
        self._captured_at = None
        self._received_at = None
        self._accepted = 0
        self._rejected = 0

    def ingest(self, raw):
        """Consume one UTF-8 JSON message. Invalid or out-of-order updates are ignored."""
        try:
            if not isinstance(raw, bytes) or not (1 <= len(raw) <= MAX_MESSAGE_BYTES):
                raise ValueError("Invalid frame size")
            message = json.loads(raw.decode("utf-8"))
            if not isinstance(message, dict) or type(message.get("version")) is not int or message["version"] != 1:
                raise ValueError("Unsupported protocol")
            session = message.get("session")
            sequence = message.get("sequence")
            kind = message.get("kind")
            changes = message.get("data")
            timestamp = message.get("captured_at")
            if not isinstance(session, str) or not (1 <= len(session) <= 64) or not all(c.isalnum() or c in "_-." for c in session):
                raise ValueError("Invalid session")
            if type(sequence) is not int or sequence < 0 or sequence > 2 ** 53:
                raise ValueError("Invalid sequence")
            if kind not in ("snapshot", "delta") or not isinstance(changes, dict):
                raise ValueError("Invalid payload")
            if type(timestamp) not in (int, float) or not (0 < timestamp <= time.time() + 300):
                raise ValueError("Invalid timestamp")
            with self._lock:
                if session == self._session and sequence <= self._sequence:
                    raise ValueError("Out-of-order sequence")
                if kind == "delta" and (session != self._session or self._data is None):
                    raise ValueError("Delta without matching snapshot")
                if kind == "snapshot":
                    updated = copy.deepcopy(changes)
                else:
                    updated = copy.deepcopy(self._data)
                    for name, value in changes.items():
                        if value is None:
                            updated.pop(name, None)
                        else:
                            updated[name] = copy.deepcopy(value)
                self._session = session
                self._sequence = sequence
                self._data = updated
                self._captured_at = timestamp
                self._received_at = time.time()
                self._accepted += 1
            return True
        except (ValueError, TypeError, UnicodeError, RecursionError, json.JSONDecodeError):
            with self._lock:
                self._rejected += 1
            return False

    def status(self):
        with self._lock:
            age = None if self._received_at is None else max(0, time.time() - min(self._received_at, self._captured_at))
            return {
                "available": self._data is not None and age <= STALE_AFTER_SECONDS,
                "age_seconds": None if age is None else round(age, 2),
                "stale": age is not None and age > STALE_AFTER_SECONDS,
                "session": self._session,
                "sequence": self._sequence if self._data is not None else None,
                "accepted_frames": self._accepted,
                "rejected_frames": self._rejected,
            }

    def snapshot(self):
        meta = self.status()
        with self._lock:
            data = copy.deepcopy(self._data) if meta["available"] else None
            captured_at = self._captured_at
        return {
            **meta,
            "source": "experimental native DLL named pipe",
            "captured_at": captured_at,
            "data": data,
        }
