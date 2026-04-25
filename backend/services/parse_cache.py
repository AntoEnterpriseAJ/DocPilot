"""Process-local content-hash cache for /parse responses.

Dedupes repeated uploads of the same PDF bytes inside a single backend
process. Bounded FIFO eviction (cap=64). Thread-safe.
"""
from __future__ import annotations

import hashlib
import threading
from collections import OrderedDict

from schemas.extraction import ExtractedDocument


_MAX_ENTRIES = 64


class ParseCache:
    def __init__(self, max_entries: int = _MAX_ENTRIES) -> None:
        self._max = max_entries
        self._lock = threading.Lock()
        self._store: "OrderedDict[str, ExtractedDocument]" = OrderedDict()

    @staticmethod
    def hash_bytes(data: bytes) -> str:
        return hashlib.sha256(data).hexdigest()

    def get(self, key: str) -> ExtractedDocument | None:
        with self._lock:
            doc = self._store.get(key)
            if doc is not None:
                # Refresh recency
                self._store.move_to_end(key)
            return doc

    def put(self, key: str, doc: ExtractedDocument) -> None:
        with self._lock:
            if key in self._store:
                self._store.move_to_end(key)
                self._store[key] = doc
                return
            self._store[key] = doc
            while len(self._store) > self._max:
                self._store.popitem(last=False)

    def clear(self) -> None:
        with self._lock:
            self._store.clear()

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


# Module-level singleton used by the /parse route.
parse_cache = ParseCache()
