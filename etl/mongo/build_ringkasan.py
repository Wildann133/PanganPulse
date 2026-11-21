"""Menghitung ringkasan bulanan dari hasil ETL dan menyimpannya ke MongoDB (tahap "hitung_analitik").

Dashboard membaca koleksi kecil ini (±500 dokumen) dan tidak menghitung ulang dari 4,6 juta dokumen,
sehingga halaman terbuka dalam hitungan milidetik.

Koleksi yang dibuat (isinya diganti penuh tiap dijalankan, jadi aman diulang):
  ringkasan_bulanan : satu dokumen per (periode, komoditas): median, rata_rata, minimum, maksimum, n_observasi, n_wilayah
  periode           : satu dokumen per bulan: tanggal_awal, tanggal_akhir, hari_observasi, jumlah_komoditas, lengkap

Median dihitung eksak dengan pandas dari CSV hasil ETL (rata-rata biasa mudah terseret nilai ekstrem).
"lengkap" = data bulan itu berakhir paling lambat 5 hari sebelum hari kerja terakhir bulan tersebut.

Jalankan dari root proyek:
    .venv-etl/bin/python etl/mongo/build_ringkasan.py
"""
import os
import time
from pathlib import Path

import pandas as pd
from pymongo import MongoClient

MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27017")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "panganpulse")
SOURCE = Path(__file__).resolve().parents[1] / "data" / "processed" / "harga_pangan_2025_2026_normalized.csv"
TOLERANSI_HARI = 5


def hitung_ringkasan(df):
    df = df.copy()
    df["periode"] = df["tanggal"].dt.strftime("%Y-%m")
    df["wilayah_id"] = df.groupby(["provinsi", "kabupaten_kota"], observed=True).ngroup()

    per_komoditas = (
        df.groupby(["periode", "komoditas_normalisasi"], observed=True)
        .agg(
            median=("harga", "median"),
            rata_rata=("harga", "mean"),
            minimum=("harga", "min"),
            maksimum=("harga", "max"),
            n_observasi=("harga", "size"),
            n_wilayah=("wilayah_id", "nunique"),
        )
        .reset_index()
        .rename(columns={"komoditas_normalisasi": "komoditas"})
    )

    per_periode = (
        df.groupby("periode")
        .agg(
            tanggal_awal=("tanggal", "min"),
            tanggal_akhir=("tanggal", "max"),
            hari_observasi=("tanggal", "nunique"),
            jumlah_komoditas=("komoditas_normalisasi", "nunique"),
        )
        .reset_index()
    )
    hari_kerja_terakhir = per_periode["periode"].map(
        lambda p: pd.Timestamp(p + "-01") + pd.offsets.BMonthEnd(0)
    )
    per_periode["lengkap"] = (hari_kerja_terakhir - per_periode["tanggal_akhir"]).dt.days <= TOLERANSI_HARI
    for kolom in ("tanggal_awal", "tanggal_akhir"):
        per_periode[kolom] = per_periode[kolom].dt.strftime("%Y-%m-%d")
    return per_komoditas, per_periode


def main():
    if not SOURCE.exists():
        raise SystemExit(f"File tidak ada: {SOURCE}\nJalankan etl/ETL.ipynb dulu untuk membuatnya.")
    start = time.time()
    df = pd.read_csv(
        SOURCE,
        usecols=["provinsi", "kabupaten_kota", "komoditas_normalisasi", "tanggal", "harga"],
        dtype={"provinsi": "category", "kabupaten_kota": "category", "komoditas_normalisasi": "category", "harga": "float64"},
        parse_dates=["tanggal"],
        encoding="utf-8-sig",
    )
    print(f"{len(df):,} baris dibaca ({time.time() - start:.0f} dtk)")

    per_komoditas, per_periode = hitung_ringkasan(df)
    per_komoditas = per_komoditas.round({"median": 2, "rata_rata": 2})

    db = MongoClient(MONGO_URI, serverSelectionTimeoutMS=3000)[MONGO_DB_NAME]
    db.ringkasan_bulanan.delete_many({})
    db.ringkasan_bulanan.insert_many(per_komoditas.to_dict("records"))
    db.periode.delete_many({})
    db.periode.insert_many(per_periode.to_dict("records"))
    db.ringkasan_bulanan.create_index([("periode", 1), ("komoditas", 1)], unique=True, name="periode_komoditas_unik")
    db.periode.create_index([("periode", 1)], unique=True, name="periode_unik")

    print(f"ringkasan_bulanan: {db.ringkasan_bulanan.count_documents({})} dokumen")
    print(f"periode          : {db.periode.count_documents({})} dokumen")
    belum = per_periode.loc[~per_periode["lengkap"], "periode"].tolist()
    print(f"periode belum lengkap: {belum or '-'}")
    print(f"selesai dalam {time.time() - start:.0f} dtk")


if __name__ == "__main__":
    main()
