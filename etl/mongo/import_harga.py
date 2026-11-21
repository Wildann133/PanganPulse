"""Import hasil ETL (CSV) ke MongoDB. Memakai upsert, jadi aman dijalankan berulang.

Sumber : etl/data/processed/harga_pangan_2025_2026_normalized.csv  (dibuat oleh etl/ETL.ipynb)
Tujuan : koleksi harga_pangan, komoditas, wilayah, etl_log

Kunci satu pengamatan: (provinsi, kabupaten_kota, komoditas, tanggal).
Wilayah sengaja dikenali dari NAMA, bukan kode_daerah, karena kode_daerah 2025 dan 2026
tidak menunjuk wilayah yang sama. kode_komoditas tidak dipakai di kunci karena data 2026 tidak memilikinya.

Jalankan dari root proyek:
    .venv-etl/bin/python etl/mongo/import_harga.py
    .venv-etl/bin/python etl/mongo/import_harga.py --limit 50000     # uji kecil
"""
import argparse
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd
from pymongo import MongoClient, UpdateOne

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "panganpulse")

PROCESSED = Path(__file__).resolve().parents[1] / "data" / "processed"
SOURCE = PROCESSED / "harga_pangan_2025_2026_normalized.csv"
ETL_LOG = PROCESSED / "etl_log.csv"

CHUNK_ROWS = 100_000
USECOLS = [
    "kode_provinsi", "provinsi", "kabupaten_kota", "kode_komoditas",
    "komoditas", "komoditas_normalisasi", "tanggal", "harga",
]


def clean_chunk(chunk):
    """Rapikan satu potongan CSV menjadi kolom yang akan disimpan."""
    chunk = chunk.copy()
    chunk["tanggal"] = pd.to_datetime(chunk["tanggal"], format="%Y-%m-%d")
    chunk["periode"] = chunk["tanggal"].dt.strftime("%Y-%m")
    chunk["komoditas_asli"] = chunk["komoditas"]
    chunk["komoditas"] = chunk["komoditas_normalisasi"]
    return chunk.drop(columns=["komoditas_normalisasi"])


def to_operations(chunk):
    ops = []
    for r in chunk.itertuples(index=False):
        key = {
            "provinsi": r.provinsi,
            "kabupaten_kota": r.kabupaten_kota,
            "komoditas": r.komoditas,
            "tanggal": r.tanggal.to_pydatetime(),
        }
        doc = {"periode": r.periode, "harga": float(r.harga)}
        if pd.notna(r.kode_provinsi):
            doc["kode_provinsi"] = int(float(r.kode_provinsi))
        if pd.notna(r.kode_komoditas):
            doc["kode_komoditas"] = int(float(r.kode_komoditas))
        if r.komoditas_asli != r.komoditas:  # simpan nama asli hanya jika sudah dinormalisasi
            doc["komoditas_asli"] = r.komoditas_asli
        ops.append(UpdateOne(key, {"$set": doc}, upsert=True))
    return ops


def upsert_reference(db, wilayah, komoditas):
    ops = [
        UpdateOne(
            {"provinsi": p, "kabupaten_kota": k},
            {"$set": {"kode_provinsi": kp}} if kp is not None else {"$setOnInsert": {}},
            upsert=True,
        )
        for (p, k), kp in sorted(wilayah.items())
    ]
    if ops:
        db.wilayah.bulk_write(ops, ordered=False)
    ops = [
        UpdateOne(
            {"nama": nama},
            {"$set": {"nama_asli": sorted(info["asli"]), "kode_komoditas": sorted(info["kode"])}},
            upsert=True,
        )
        for nama, info in sorted(komoditas.items())
    ]
    if ops:
        db.komoditas.bulk_write(ops, ordered=False)


def import_etl_log(db):
    if not ETL_LOG.exists():
        return 0
    log = pd.read_csv(ETL_LOG, encoding="utf-8-sig")
    ops = []
    for row in log.to_dict("records"):
        row = {k: (int(v) if hasattr(v, "item") and isinstance(v.item(), int) else v) for k, v in row.items()}
        ops.append(UpdateOne({"tahap": "transform", "file_sumber": row["file_sumber"]}, {"$set": row}, upsert=True))
    db.etl_log.bulk_write(ops, ordered=False)
    return len(ops)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None, help="hanya baca N baris pertama (untuk uji)")
    args = parser.parse_args()

    if not SOURCE.exists():
        raise SystemExit(f"File tidak ada: {SOURCE}\nJalankan etl/ETL.ipynb dulu untuk membuatnya.")

    db = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)[MONGO_DB_NAME]
    before = db.harga_pangan.estimated_document_count()
    print(f"database {MONGO_DB_NAME}: harga_pangan berisi {before:,} dokumen sebelum import")

    start = time.time()
    rows_read = 0
    wilayah, komoditas = {}, {}
    reader = pd.read_csv(
        SOURCE, usecols=USECOLS, dtype=str, encoding="utf-8-sig",
        chunksize=CHUNK_ROWS, nrows=args.limit,
    )
    for chunk in reader:
        chunk = clean_chunk(chunk)
        chunk["harga"] = pd.to_numeric(chunk["harga"])
        for p, k, kp in chunk[["provinsi", "kabupaten_kota", "kode_provinsi"]].drop_duplicates().itertuples(index=False):
            wilayah[(p, k)] = int(float(kp)) if pd.notna(kp) else None
        for nama, asli, kode in chunk[["komoditas", "komoditas_asli", "kode_komoditas"]].drop_duplicates().itertuples(index=False):
            info = komoditas.setdefault(nama, {"asli": set(), "kode": set()})
            info["asli"].add(asli)
            if pd.notna(kode):
                info["kode"].add(int(float(kode)))
        db.harga_pangan.bulk_write(to_operations(chunk), ordered=False)
        rows_read += len(chunk)
        print(f"  {rows_read:>10,} baris diproses  ({time.time() - start:5.0f} dtk)", flush=True)

    upsert_reference(db, wilayah, komoditas)
    n_log = import_etl_log(db)
    total = db.harga_pangan.count_documents({})
    db.etl_log.insert_one({
        "tahap": "load",
        "waktu": datetime.now(timezone.utc),
        "sumber": SOURCE.name,
        "baris_dibaca": rows_read,
        "dokumen_harga_pangan": total,
        "durasi_detik": round(time.time() - start, 1),
    })

    print("\nSelesai")
    print(f"  baris dibaca CSV        : {rows_read:,}")
    print(f"  dokumen harga_pangan    : {total:,}  (sebelumnya {before:,})")
    print(f"  wilayah / komoditas     : {db.wilayah.count_documents({}):,} / {db.komoditas.count_documents({}):,}")
    print(f"  catatan etl_log (sumber): {n_log}")
    print(f"  durasi                  : {time.time() - start:.0f} dtk")


if __name__ == "__main__":
    main()
