"""Logika Dashboard Overview: membaca ringkasan dari MongoDB dan menyusun data untuk /api/ringkasan.

Koleksi `ringkasan_bulanan` dan `periode` dibuat oleh etl/mongo/build_ringkasan.py (dihitung saat ETL),
jadi view tidak pernah menghitung ulang dari jutaan dokumen mentah.
"""

UKURAN_VALID = ("median", "rata_rata")   # daftar putih untuk parameter `ukuran`
AMBANG_LONJAKAN = 10.0                   # kenaikan (%) yang dianggap lonjakan
JUMLAH_PERINGKAT = 5


class ParameterTidakValid(ValueError):
    """Parameter dari browser tidak lolos daftar putih (jadi HTTP 400)."""


class DataBelumSiap(RuntimeError):
    """Koleksi ringkasan belum dibuat (jadi HTTP 503)."""


def pilih_periode_awal(daftar_periode):
    """Periode lengkap terakhir; bulan berjalan yang belum lengkap tidak dipilih sebagai awal."""
    lengkap = [p["periode"] for p in daftar_periode if p["lengkap"]]
    return lengkap[-1] if lengkap else daftar_periode[-1]["periode"]


def periode_sebelumnya(daftar_periode, periode):
    nama = [p["periode"] for p in daftar_periode]
    i = nama.index(periode)
    return nama[i - 1] if i > 0 else None


def bandingkan(sekarang, sebelumnya, ukuran):
    """sekarang/sebelumnya: {komoditas: dokumen ringkasan}. Perubahan hanya untuk komoditas yang ada di keduanya."""
    hasil = []
    for nama, dok in sekarang.items():
        item = {
            "nama": nama,
            "nilai": dok[ukuran],
            "n_observasi": dok["n_observasi"],
            "nilai_pembanding": None,
            "perubahan_pct": None,
        }
        lawan = sebelumnya.get(nama)
        if lawan and lawan[ukuran]:
            item["nilai_pembanding"] = lawan[ukuran]
            item["perubahan_pct"] = round((dok[ukuran] / lawan[ukuran] - 1) * 100, 2)
        hasil.append(item)
    return hasil


def susun_kpi(komoditas):
    """Angka ringkas dari daftar hasil `bandingkan`."""
    berubah = [k for k in komoditas if k["perubahan_pct"] is not None]
    naik = max(berubah, key=lambda k: k["perubahan_pct"], default=None)
    turun = min(berubah, key=lambda k: k["perubahan_pct"], default=None)
    by_nilai = sorted(komoditas, key=lambda k: k["nilai"], reverse=True)
    return {
        "jumlah_komoditas": len(komoditas),
        "naik_terbesar": naik if naik and naik["perubahan_pct"] > 0 else None,
        "turun_terbesar": turun if turun and turun["perubahan_pct"] < 0 else None,
        "tertinggi": by_nilai[:JUMLAH_PERINGKAT],
        "terendah": by_nilai[::-1][:JUMLAH_PERINGKAT],
        "lonjakan": sorted(
            (k for k in berubah if k["perubahan_pct"] >= AMBANG_LONJAKAN),
            key=lambda k: k["perubahan_pct"],
            reverse=True,
        ),
    }


def ambil_status(db):
    terakhir = db.periode.find_one(sort=[("periode", -1)])
    ditolak = sum(d.get("baris_ditolak", 0) for d in db.etl_log.find({"tahap": "transform"}))
    muat = db.etl_log.find_one({"tahap": "load"}, sort=[("waktu", -1)])
    return {
        "data_terakhir": terakhir["tanggal_akhir"] if terakhir else None,
        "total_dokumen": db.harga_pangan.estimated_document_count(),
        "baris_ditolak": ditolak,
        "dimuat_pada": muat["waktu"].isoformat() if muat and muat.get("waktu") else None,
    }


def bangun_ringkasan(db, periode=None, ukuran="median"):
    if ukuran not in UKURAN_VALID:
        raise ParameterTidakValid(f"ukuran harus salah satu dari {', '.join(UKURAN_VALID)}")

    daftar = list(db.periode.find({}, {"_id": 0}).sort("periode", 1))
    if not daftar:
        raise DataBelumSiap("Ringkasan belum dibuat. Jalankan etl/mongo/build_ringkasan.py")
    tersedia = [p["periode"] for p in daftar]

    if periode is None:
        periode = pilih_periode_awal(daftar)
    elif periode not in tersedia:
        raise ParameterTidakValid("periode tidak tersedia")
    pembanding = periode_sebelumnya(daftar, periode)

    semua = {}
    for d in db.ringkasan_bulanan.find({}, {"_id": 0}).sort("periode", 1):
        semua.setdefault(d["periode"], {})[d["komoditas"]] = d

    komoditas = bandingkan(semua.get(periode, {}), semua.get(pembanding, {}), ukuran)
    komoditas.sort(key=lambda k: (k["perubahan_pct"] is None, -(k["perubahan_pct"] or 0)))
    info = next(p for p in daftar if p["periode"] == periode)

    lengkap = {p["periode"] for p in daftar if p["lengkap"]}
    tren = {}
    for per in tersedia:
        if per not in lengkap:   # bulan berjalan tidak dimasukkan ke garis tren
            continue
        for nama, d in semua.get(per, {}).items():
            tren.setdefault(nama, []).append({"periode": per, "nilai": d[ukuran]})

    catatan = []
    if not info["lengkap"]:
        catatan.append(
            f"Periode {periode} belum lengkap (data sampai {info['tanggal_akhir']}, {info['hari_observasi']} hari). "
            "Perubahan terhadap bulan penuh bisa menyesatkan."
        )
    prev_info = next((p for p in daftar if p["periode"] == pembanding), None)
    if prev_info and prev_info["jumlah_komoditas"] != info["jumlah_komoditas"]:
        catatan.append(
            f"Jumlah komoditas berbeda ({prev_info['jumlah_komoditas']} pada {pembanding}, "
            f"{info['jumlah_komoditas']} pada {periode}); perubahan hanya dihitung untuk komoditas yang ada di keduanya."
        )

    return {
        "periode": periode,
        "pembanding": pembanding,
        "ukuran": ukuran,
        "ambang_lonjakan": AMBANG_LONJAKAN,
        "periode_tersedia": [
            {"periode": p["periode"], "lengkap": p["lengkap"], "hari": p["hari_observasi"]} for p in daftar
        ],
        "kpi": susun_kpi(komoditas),
        "komoditas": komoditas,
        "tren": tren,
        "status": ambil_status(db),
        "catatan": catatan,
    }
