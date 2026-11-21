"""Koneksi MongoDB untuk Django (pymongo langsung, tanpa ORM).

Alamat diambil dari variabel lingkungan MONGO_URI dan MONGO_DB_NAME;
bila tidak ada, dipakai nilai bawaan untuk pengembangan lokal (docker/docker-compose.yml).
"""
import os

from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "panganpulse")

_client = None


def get_client():
    """Satu MongoClient dipakai bersama (client pymongo aman dipakai lintas thread)."""
    global _client
    if _client is None:
        _client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=2000)
    return _client


def get_db():
    return get_client()[MONGO_DB_NAME]


def ping():
    """Mengembalikan (True, versi_server) bila MongoDB terjangkau, selain itu (False, pesan_error)."""
    try:
        info = get_client().server_info()
        return True, info.get("version", "?")
    except Exception as exc:  # pymongo melempar beberapa jenis error koneksi
        return False, f"{type(exc).__name__}"
