"""
Lapisan akses data Regional Comparison.

View tidak langsung bicara ke MongoDB; semua query ada di sini supaya mudah
dites dan diganti. Data berasal dari koleksi yang diisi pipeline ETL/Airflow.
"""
from utils.mongo import get_db  # koneksi MongoDB bersama milik tim (backend/utils/mongo.py)

LEVELS = {"provinsi": "Provinsi", "kabupaten_kota": "Kabupaten/Kota"}

COLLECTION_PRICES = "regional_comparison_prices"
COLLECTION_SUMMARY = "regional_comparison_summary"


def _prices():
    return get_db()[COLLECTION_PRICES]


def _summary():
    return get_db()[COLLECTION_SUMMARY]

def get_period_status():
    """
    {periode: lengkap?} dari koleksi `periode` yang dibuat ETL dashboard (build_ringkasan.py).
    Dipakai agar halaman ini tidak memilih bulan yang datanya belum lengkap sebagai tampilan awal,
    sama seperti dashboard. Kosong jika koleksi itu belum ada.
    """
    rows = get_db()["periode"].find({}, {"_id": 0, "periode": 1, "lengkap": 1})
    return {r["periode"]: bool(r.get("lengkap")) for r in rows}

def normalize_level(level):
    return level if level in LEVELS else "provinsi"


def list_periods():
    """Daftar periode (YYYY-MM), terbaru dulu."""
    return sorted(_summary().distinct("periode"), reverse=True)


def list_commodities():
    return sorted(_summary().distinct("komoditas"))


def get_summary(level, periode, komoditas):
    """Ringkasan (termurah, termahal, selisih, CV) satu komoditas."""
    return _summary().find_one(
        {"level": level, "periode": periode, "komoditas": komoditas},
        {"_id": 0},
    )


def get_ranking(level, periode, komoditas):
    """Semua wilayah untuk satu komoditas, urut peringkat 1 (termahal) dst."""
    return list(
        _prices()
        .find({"level": level, "periode": periode, "komoditas": komoditas}, {"_id": 0})
        .sort("peringkat", 1)
    )


def get_cv_ranking(level, periode):
    """Komoditas diurutkan dari disparitas (CV) tertinggi ke terendah."""
    return list(
        _summary()
        .find(
            {"level": level, "periode": periode, "cv_persen": {"$ne": None}},
            {"_id": 0},
        )
        .sort("cv_persen", -1)
    )
