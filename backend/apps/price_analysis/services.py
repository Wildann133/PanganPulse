from datetime import datetime, timedelta
import re

from utils.mongo import get_db


def _parse_date(date_str: str | None) -> datetime | None:
    """Mengonversi string YYYY-MM-DD menjadi objek datetime untuk query BSON Date MongoDB."""
    if not date_str:
        return None
    cleaned = date_str.strip()
    if not re.match(r"^\d{4}-\d{2}-\d{2}$", cleaned):
        raise ValueError(f"Format tanggal tidak valid: '{date_str}'. Gunakan format YYYY-MM-DD.")
    return datetime.strptime(cleaned, "%Y-%m-%d")


def _validate_periode(periode_str: str | None) -> str | None:
    """Memvalidasi format periode YYYY-MM (contoh: 2025-01)."""
    if not periode_str:
        return None
    cleaned = periode_str.strip()
    if not re.match(r"^\d{4}-\d{2}$", cleaned):
        raise ValueError(f"Format periode tidak valid: '{periode_str}'. Gunakan format YYYY-MM.")
    return cleaned


def _format_date(val) -> str:
    """Memastikan nilai datetime atau string tanggal diformat menjadi YYYY-MM-DD."""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    return str(val)[:10]


def get_filter_options() -> dict:
    """
    Mengambil daftar whitelist komoditas, wilayah (kabupaten_kota & provinsi),
    serta daftar periode yang tersedia di MongoDB.
    """
    db = get_db()

    # Ambil dari koleksi referensi (cepat) dengan fallback ke harga_pangan
    komoditas_docs = list(db.komoditas.find({}, {"_id": 0, "nama": 1}).sort("nama", 1))
    if komoditas_docs:
        komoditas_list = [d["nama"] for d in komoditas_docs if d.get("nama")]
    else:
        komoditas_list = sorted([k for k in db.harga_pangan.distinct("komoditas") if k])

    wilayah_docs = list(
        db.wilayah.find({}, {"_id": 0, "provinsi": 1, "kabupaten_kota": 1}).sort(
            [("provinsi", 1), ("kabupaten_kota", 1)]
        )
    )
    if wilayah_docs:
        kabupaten_list = sorted({d["kabupaten_kota"] for d in wilayah_docs if d.get("kabupaten_kota")})
        provinsi_list = sorted({d["provinsi"] for d in wilayah_docs if d.get("provinsi")})
    else:
        kabupaten_list = sorted([w for w in db.harga_pangan.distinct("kabupaten_kota") if w])
        provinsi_list = sorted([p for p in db.harga_pangan.distinct("provinsi") if p])
        wilayah_docs = []

    periode_list = sorted([p for p in db.harga_pangan.distinct("periode") if p])

    bounds = list(db.harga_pangan.aggregate([
        {
            "$group": {
                "_id": None,
                "min_date": {"$min": "$tanggal"},
                "max_date": {"$max": "$tanggal"},
            }
        }
    ]))

    min_date = _format_date(bounds[0]["min_date"]) if bounds and bounds[0].get("min_date") else "2025-01-01"
    max_date = _format_date(bounds[0]["max_date"]) if bounds and bounds[0].get("max_date") else "2026-12-31"

    return {
        "komoditas": komoditas_list,
        "kabupaten_kota": kabupaten_list,
        "provinsi": provinsi_list,
        "wilayah_detail": wilayah_docs,
        "periode": periode_list,
        "min_date": min_date,
        "max_date": max_date,
    }


def get_price_trend(
    komoditas: str,
    kabupaten_kota: str,
    periode: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict:
    """
    Menjalankan aggregation pipeline pada koleksi harga_pangan untuk mendapatkan
    time-series tren harga dan ringkasan statistik perubahan harga.
    """
    if not komoditas or not kabupaten_kota:
        raise ValueError("Parameter 'komoditas' dan 'kabupaten_kota' (atau 'wilayah') wajib diisi.")

    periode_clean = _validate_periode(periode)
    start_dt = _parse_date(start_date)
    end_dt = _parse_date(end_date)

    if start_dt and end_dt and start_dt > end_dt:
        raise ValueError("Tanggal mulai (start_date) tidak boleh lebih besar dari tanggal akhir (end_date).")

    # Validasi whitelist sesuai desain keamanan sistem
    options = get_filter_options()
    if options["komoditas"] and komoditas not in options["komoditas"]:
        raise ValueError(f"Komoditas tidak valid: {komoditas}")
    if options["kabupaten_kota"] and kabupaten_kota not in options["kabupaten_kota"]:
        raise ValueError(f"Wilayah (kabupaten/kota) tidak valid: {kabupaten_kota}")

    db = get_db()
    match_stage: dict = {
        "komoditas": komoditas,
        "kabupaten_kota": kabupaten_kota,
    }

    if periode_clean:
        match_stage["periode"] = periode_clean
    elif start_dt or end_dt:
        date_query: dict = {}
        if start_dt:
            date_query["$gte"] = start_dt
        if end_dt:
            date_query["$lt"] = end_dt + timedelta(days=1)
        match_stage["tanggal"] = date_query

    pipeline = [
        {"$match": match_stage},
        {
            "$group": {
                "_id": "$tanggal",
                "provinsi": {"$first": "$provinsi"},
                "harga_rata2": {"$avg": "$harga"},
                "harga_min": {"$min": "$harga"},
                "harga_max": {"$max": "$harga"},
                "jumlah_observasi": {"$sum": 1},
            }
        },
        {"$sort": {"_id": 1}},
    ]

    rows = list(db.harga_pangan.aggregate(pipeline))

    if not rows:
        return {
            "meta": {
                "komoditas": komoditas,
                "kabupaten_kota": kabupaten_kota,
                "provinsi": None,
                "periode": periode_clean,
                "start_date": start_date,
                "end_date": end_date,
                "total_points": 0,
            },
            "summary": None,
            "series": [],
        }

    series = []
    prices = []
    prev_price = None

    for row in rows:
        tanggal_str = _format_date(row["_id"])
        harga = round(float(row["harga_rata2"]), 2)
        prices.append(harga)

        delta_rp = round(harga - prev_price, 2) if prev_price is not None else 0.0
        delta_pct = round((delta_rp / prev_price) * 100, 2) if prev_price else 0.0

        series.append({
            "tanggal": tanggal_str,
            "harga": harga,
            "harga_min": round(float(row["harga_min"]), 2),
            "harga_max": round(float(row["harga_max"]), 2),
            "perubahan_rp": delta_rp,
            "perubahan_persen": delta_pct,
            "jumlah_observasi": int(row["jumlah_observasi"]),
        })
        prev_price = harga

    harga_awal = prices[0]
    harga_akhir = prices[-1]
    harga_rata2 = round(sum(prices) / len(prices), 2)

    peak_item = max(series, key=lambda x: x["harga"])
    trough_item = min(series, key=lambda x: x["harga"])

    selisih_rp = round(harga_akhir - harga_awal, 2)
    selisih_persen = round((selisih_rp / harga_awal) * 100, 2) if harga_awal else 0.0

    # Coefficient of Variation (CV) untuk menentukan tingkat fluktuasi harga
    mean_val = sum(prices) / len(prices)
    variance = sum((p - mean_val) ** 2 for p in prices) / len(prices)
    std_dev = variance ** 0.5
    cv_percent = round((std_dev / mean_val) * 100, 2) if mean_val else 0.0

    if cv_percent > 5.0:
        status_tren = "Berfluktuasi Tinggi"
    elif selisih_persen > 1.0:
        status_tren = "Cenderung Naik"
    elif selisih_persen < -1.0:
        status_tren = "Cenderung Turun"
    else:
        status_tren = "Stabil"

    return {
        "meta": {
            "komoditas": komoditas,
            "kabupaten_kota": kabupaten_kota,
            "provinsi": rows[0].get("provinsi"),
            "periode": periode_clean,
            "start_date": series[0]["tanggal"],
            "end_date": series[-1]["tanggal"],
            "total_points": len(series),
        },
        "summary": {
            "harga_awal": harga_awal,
            "harga_akhir": harga_akhir,
            "harga_rata_rata": harga_rata2,
            "harga_tertinggi": peak_item["harga"],
            "tanggal_tertinggi": peak_item["tanggal"],
            "harga_terendah": trough_item["harga"],
            "tanggal_terendah": trough_item["tanggal"],
            "selisih_rp": selisih_rp,
            "selisih_persen": selisih_persen,
            "volatilitas_cv": cv_percent,
            "status_tren": status_tren,
        },
        "series": series,
    }


def get_price_detail(komoditas: str, kabupaten_kota: str, tanggal: str) -> dict:
    """
    Mengambil detail dokumen pada titik tanggal tertentu saat user mengklik titik grafik Plotly (/api/detail).
    """
    if not komoditas or not kabupaten_kota or not tanggal:
        raise ValueError("Parameter 'komoditas', 'kabupaten_kota' (atau 'wilayah'), dan 'tanggal' wajib diisi.")

    dt_start = _parse_date(tanggal)
    dt_end = dt_start + timedelta(days=1)

    db = get_db()
    raw_records = list(
        db.harga_pangan.find(
            {
                "komoditas": komoditas,
                "kabupaten_kota": kabupaten_kota,
                "tanggal": {"$gte": dt_start, "$lt": dt_end},
            },
            {"_id": 0},
        )
    )

    # Konversi datetime ke string agar aman diserialisasi oleh JsonResponse
    records = []
    for rec in raw_records:
        item = dict(rec)
        if "tanggal" in item:
            item["tanggal"] = _format_date(item["tanggal"])
        records.append(item)

    anomali = []
    if "anomali_harga" in db.list_collection_names():
        raw_anomali = list(
            db.anomali_harga.find(
                {
                    "komoditas": komoditas,
                    "kabupaten_kota": kabupaten_kota,
                    "tanggal": {"$gte": dt_start, "$lt": dt_end},
                },
                {"_id": 0},
            )
        )
        for a in raw_anomali:
            item = dict(a)
            if "tanggal" in item:
                item["tanggal"] = _format_date(item["tanggal"])
            anomali.append(item)

    return {
        "komoditas": komoditas,
        "kabupaten_kota": kabupaten_kota,
        "tanggal": tanggal.strip(),
        "total_records": len(records),
        "records": records,
        "anomali": anomali,
    }