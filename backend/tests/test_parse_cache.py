"""Tests for the process-local parse cache."""
from __future__ import annotations

import pytest

from schemas.extraction import ExtractedDocument
from services.parse_cache import ParseCache


def _doc(label: str) -> ExtractedDocument:
    return ExtractedDocument(
        document_type=label,
        summary=f"summary for {label}",
        source_route="text_pdf",
    )


def test_cache_hit_returns_same_object():
    cache = ParseCache(max_entries=4)
    key = ParseCache.hash_bytes(b"hello")
    doc = _doc("a")
    cache.put(key, doc)
    assert cache.get(key) is doc


def test_cache_miss_returns_none():
    cache = ParseCache(max_entries=4)
    assert cache.get(ParseCache.hash_bytes(b"missing")) is None


def test_cache_evicts_oldest_when_full():
    cache = ParseCache(max_entries=2)
    k1 = ParseCache.hash_bytes(b"1")
    k2 = ParseCache.hash_bytes(b"2")
    k3 = ParseCache.hash_bytes(b"3")
    cache.put(k1, _doc("1"))
    cache.put(k2, _doc("2"))
    cache.put(k3, _doc("3"))  # should evict k1
    assert cache.get(k1) is None
    assert cache.get(k2) is not None
    assert cache.get(k3) is not None
    assert len(cache) == 2


def test_cache_get_refreshes_recency():
    cache = ParseCache(max_entries=2)
    k1 = ParseCache.hash_bytes(b"1")
    k2 = ParseCache.hash_bytes(b"2")
    k3 = ParseCache.hash_bytes(b"3")
    cache.put(k1, _doc("1"))
    cache.put(k2, _doc("2"))
    # Touch k1 so it becomes most-recent
    assert cache.get(k1) is not None
    cache.put(k3, _doc("3"))  # should evict k2 now, not k1
    assert cache.get(k1) is not None
    assert cache.get(k2) is None
    assert cache.get(k3) is not None


def test_hash_bytes_is_deterministic_and_distinct():
    assert ParseCache.hash_bytes(b"a") == ParseCache.hash_bytes(b"a")
    assert ParseCache.hash_bytes(b"a") != ParseCache.hash_bytes(b"b")
