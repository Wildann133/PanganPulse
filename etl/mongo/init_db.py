"""Membuat koleksi dan indeks MongoDB untuk PanganPulse. Aman dijalankan berulang.

Jalankan dari root proyek:
    .venv-etl/bin/python etl/mongo/init_db.py
"""
import os

from pymongo import ASCENDING, MongoClient

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "panganpulse")

COLLECTIONS = ["harga_pangan", "komoditas", "wilayah", "etl_log"]

# (nama koleksi, kunci indeks, opsi)
INDEXES = [
    # Indeks dari desain: filter per komoditas / wilayah dalam satu periode.
    ("harga_pangan", [("komoditas", ASCENDING), ("periode", ASCENDING)], {"name": "komoditas_periode"}),
    ("harga_pangan", [("kabupaten_kota", ASCENDING), ("periode", ASCENDING)], {"name": "wilayah_periode"}),
    # Kunci satu pengamatan: dipakai upsert dan mencegah duplikat.
    (
        "harga_pangan",
        [("provinsi", ASCENDING), ("kabupaten_kota", ASCENDING), ("komoditas", ASCENDING), ("tanggal", ASCENDING)],
        {"name": "pengamatan_unik", "unique": True},
    ),
    ("komoditas", [("nama", ASCENDING)], {"name": "nama_unik", "unique": True}),
    ("wilayah", [("provinsi", ASCENDING), ("kabupaten_kota", ASCENDING)], {"name": "wilayah_unik", "unique": True}),
]


def main():
    db = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)[MONGO_DB_NAME]
    existing = set(db.list_collection_names())
    for name in COLLECTIONS:
        if name not in existing:
            db.create_collection(name)
            print(f"koleksi dibuat : {name}")
        else:
            print(f"koleksi sudah ada: {name}")
    for coll, keys, opts in INDEXES:
        db[coll].create_index(keys, **opts)
    print()
    for name in COLLECTIONS:
        idx = [i["name"] for i in db[name].list_indexes()]
        print(f"{name:14s} indeks: {', '.join(idx)}")


if __name__ == "__main__":
    main()
