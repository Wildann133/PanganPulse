"""
Tahap LOAD: memasukkan hasil Regional Comparison ke MongoDB.

Strategi sederhana: hapus isi koleksi lama, lalu isi ulang (idempotent -
dijalankan berkali-kali hasilnya sama, tidak menggandakan data).
"""
import pandas as pd
from pymongo import ASCENDING, MongoClient

from .config import (
    COLLECTION_PRICES,
    COLLECTION_SUMMARY,
    COMPARISON_PRICES_CSV,
    COMPARISON_SUMMARY_CSV,
    MONGO_DB_NAME,
    MONGO_URI,
)

BATCH_SIZE = 20_000


def get_db():
    client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
    return client[MONGO_DB_NAME]


def _to_records(df):
    """DataFrame -> list of dict dengan NaN diganti None (agar valid di Mongo)."""
    clean = df.astype(object).where(df.notna(), None)
    return clean.to_dict("records")


def _replace_collection(collection, df):
    collection.delete_many({})
    records = _to_records(df)
    for start in range(0, len(records), BATCH_SIZE):
        collection.insert_many(records[start:start + BATCH_SIZE])
    return len(records)


def create_indexes(db):
    db[COLLECTION_PRICES].create_index(
        [("level", ASCENDING), ("periode", ASCENDING),
         ("komoditas", ASCENDING), ("peringkat", ASCENDING)]
    )
    db[COLLECTION_PRICES].create_index(
        [("level", ASCENDING), ("kode_wilayah", ASCENDING),
         ("komoditas", ASCENDING), ("periode", ASCENDING)]
    )
    db[COLLECTION_SUMMARY].create_index(
        [("level", ASCENDING), ("periode", ASCENDING), ("komoditas", ASCENDING)],
        unique=True,
    )


def run_load(db=None):
    """Baca CSV hasil metrik lalu muat ke MongoDB."""
    db = db if db is not None else get_db()

    prices = pd.read_csv(
        COMPARISON_PRICES_CSV, dtype={"kode_wilayah": "string"}
    )
    summary = pd.read_csv(COMPARISON_SUMMARY_CSV)

    n_prices = _replace_collection(db[COLLECTION_PRICES], prices)
    n_summary = _replace_collection(db[COLLECTION_SUMMARY], summary)
    create_indexes(db)

    return {
        "database": db.name,
        "dokumen_harga": n_prices,
        "dokumen_ringkasan": n_summary,
    }


def validate_load(db=None):
    """Cek sederhana: jumlah dokumen di Mongo = jumlah baris di CSV."""
    db = db if db is not None else get_db()

    expected_prices = len(pd.read_csv(COMPARISON_PRICES_CSV, usecols=["level"]))
    expected_summary = len(pd.read_csv(COMPARISON_SUMMARY_CSV, usecols=["level"]))
    got_prices = db[COLLECTION_PRICES].count_documents({})
    got_summary = db[COLLECTION_SUMMARY].count_documents({})

    if (got_prices, got_summary) != (expected_prices, expected_summary):
        raise ValueError(
            "Jumlah dokumen tidak cocok: "
            f"harga {got_prices}/{expected_prices}, "
            f"ringkasan {got_summary}/{expected_summary}"
        )
    return {"dokumen_harga": got_prices, "dokumen_ringkasan": got_summary, "status": "OK"}
