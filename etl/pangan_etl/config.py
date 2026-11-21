"""
Konfigurasi bersama untuk pipeline ETL PanganPulse (fitur Regional Comparison).

Semua path, aturan membaca file mentah, dan nama koleksi MongoDB dikumpulkan di
sini supaya hanya ada SATU tempat yang perlu diubah.
"""
import os
from pathlib import Path

# ---------------------------------------------------------------------------
# Lokasi folder
# ---------------------------------------------------------------------------
# File ini ada di etl/pangan_etl/config.py  ->  parents[1] adalah folder etl/
ETL_DIR = Path(__file__).resolve().parents[1]
RAW_DIR = ETL_DIR / "data" / "dataset"        # CSV mentah dari sumber
PROCESSED_DIR = ETL_DIR / "data" / "processed"  # hasil olahan

# File antara (intermediate) yang dibuat pipeline ini
MONTHLY_PRICES_CSV = PROCESSED_DIR / "regional_monthly_prices.csv"
COMPARISON_PRICES_CSV = PROCESSED_DIR / "regional_comparison_prices.csv"
COMPARISON_SUMMARY_CSV = PROCESSED_DIR / "regional_comparison_summary.csv"

# ---------------------------------------------------------------------------
# Format file mentah (disalin dari ETL.ipynb, bagian 1)
# ---------------------------------------------------------------------------
MONTHS = [
    "januari", "februari", "maret", "april", "mei", "juni",
    "juli", "agustus", "september", "oktober", "november", "desember",
]

RAW_FILES = [f"{m}.csv" for m in MONTHS] + ["data-2026.csv"]

SOURCE_FORMATS = {
    name: {
        "encoding": "utf-8-sig",
        "sep": ",",
        "date_format": "%d/%m/%y",
        "thousands_separator": None,
    }
    for name in RAW_FILES[:-1]
}
SOURCE_FORMATS["data-2026.csv"] = {
    "encoding": "utf-16",
    "sep": "\t",
    "date_format": "%d/%m/%Y",
    "thousands_separator": ".",
}

# Nama kolom sumber -> nama kolom standar (disalin dari ETL.ipynb)
COLUMNS_RENAME = {
    "Kode Provinsi": "kode_provinsi",
    "Provinsi": "provinsi",
    "Kode Daerah": "kode_daerah",
    "Kode Wilayah": "kode_daerah",
    "Kabupaten Kota": "kabupaten_kota",
    "Komoditas": "komoditas",
}
# Kolom yang BUKAN kolom tanggal
NON_DATE_COLUMNS = set(COLUMNS_RENAME) | {"No", "HET/HA", "COICOP"}

# Mapping nama komoditas final (disalin dari ETL.ipynb, bagian 12).
# PENTING: jika tim mengubah mapping di notebook, ubah juga di sini.
COMMODITY_MAPPING = {
    "BAWANG PUTIH HONAN": "BAWANG PUTIH",
    "CABAI MERAH BESAR": "CABAI MERAH",
    "CABAI RAWIT MERAH": "CABAI RAWIT",
    "DAGING SAPI PAHA BELAKANG": "DAGING SAPI",
    "GULA PASIR CURAH": "GULA PASIR",
    "MINYAK GORENG SAWIT CURAH": "MINYAK GORENG",
}

# ---------------------------------------------------------------------------
# Ambang kategori disparitas berdasarkan Coefficient of Variation (CV, dalam %)
# Ini ambang pilihan tim (bukan standar baku) - boleh diubah dan dijelaskan
# di laporan.
# ---------------------------------------------------------------------------
CV_LOW_MAX = 15.0     # CV < 15%        -> "Rendah"
CV_MEDIUM_MAX = 30.0  # 15% <= CV < 30% -> "Sedang", selebihnya "Tinggi"

# ---------------------------------------------------------------------------
# MongoDB
# ---------------------------------------------------------------------------
# Default 27018 = port MongoDB milik docker-compose proyek ini (agar tidak
# bentrok dengan MongoDB lokal di port 27017). Bisa ditimpa lewat variabel
# lingkungan MONGO_URI.
MONGO_URI = os.environ.get("MONGO_URI", "mongodb://localhost:27018")
MONGO_DB_NAME = os.environ.get("MONGO_DB_NAME", "pangan_pulse")

COLLECTION_PRICES = "regional_comparison_prices"    # 1 dokumen = 1 wilayah
COLLECTION_SUMMARY = "regional_comparison_summary"  # 1 dokumen = 1 komoditas
