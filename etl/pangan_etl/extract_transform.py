"""
Tahap EXTRACT + TRANSFORM untuk fitur Regional Comparison.

Alur:
  CSV mentah (wide, kolom = tanggal)
    -> long (1 baris = 1 wilayah, 1 komoditas, 1 tanggal)
    -> bersihkan harga, buang duplikat
    -> samakan nama komoditas (COMMODITY_MAPPING)
    -> ringkas jadi rata-rata harga BULANAN per kabupaten/kota

Hasil akhir disimpan ke data/processed/regional_monthly_prices.csv
Logika pembersihan sama dengan ETL.ipynb, hanya dijadikan fungsi .py agar bisa
dijalankan otomatis oleh Airflow.
"""
import pandas as pd

from .config import (
    COLUMNS_RENAME,
    COMMODITY_MAPPING,
    MONTHLY_PRICES_CSV,
    NON_DATE_COLUMNS,
    PROCESSED_DIR,
    RAW_DIR,
    RAW_FILES,
    SOURCE_FORMATS,
)

ID_COLUMNS = ["kode_daerah", "provinsi", "kabupaten_kota", "komoditas"]

# Kunci wilayah yang STABIL antar-tahun. Kode daerah TIDAK dipakai sebagai kunci
# karena sumber 2025 dan 2026 memakai kode berbeda untuk wilayah yang sama
# (contoh: Kota Dumai 1473 di 2025, 1472 di 2026; kode provinsi Papua juga
# bergeser). Nama provinsi + nama kab/kota sama di kedua tahun.
REGION_KEY = ["provinsi", "kabupaten_kota"]


def _normalize_region_name(values):
    """'Kab Timor Tengah Selatan' dan 'Kab. Timor Tengah Selatan' dianggap sama."""
    return values.str.strip().str.replace(
        r"^(Kab|Kota)\b\.?\s*", r"\1. ", regex=True, case=False
    )


def check_raw_files():
    """Pastikan semua file mentah ada. Mengembalikan ringkasan kecil."""
    missing = [name for name in RAW_FILES if not (RAW_DIR / name).is_file()]
    if missing:
        raise FileNotFoundError(f"File mentah belum lengkap di {RAW_DIR}: {missing}")
    return {"jumlah_file": len(RAW_FILES), "folder": str(RAW_DIR)}


def _read_raw(path):
    fmt = SOURCE_FORMATS[path.name]
    df = pd.read_csv(path, sep=fmt["sep"], encoding=fmt["encoding"], dtype="string")
    df.columns = [c.strip() for c in df.columns]  # beberapa header punya spasi
    return df


def clean_one_file(path):
    """
    Membersihkan satu file mentah.
    Mengembalikan (agregat_bulanan, tabel_nama_wilayah, statistik_kualitas).
    """
    fmt = SOURCE_FORMATS[path.name]
    raw = _read_raw(path)

    date_columns = [c for c in raw.columns if c not in NON_DATE_COLUMNS]
    data = raw.rename(columns=COLUMNS_RENAME)[ID_COLUMNS + date_columns].copy()

    # Rapikan teks identitas
    data["kode_daerah"] = (
        data["kode_daerah"].str.strip().str.replace(r"\.0$", "", regex=True)
    )
    data["provinsi"] = data["provinsi"].str.strip()
    data["kabupaten_kota"] = _normalize_region_name(data["kabupaten_kota"])
    data["komoditas"] = data["komoditas"].str.strip().str.upper()
    data[ID_COLUMNS] = data[ID_COLUMNS].fillna("")

    # wide -> long
    long = data.melt(
        id_vars=ID_COLUMNS,
        value_vars=date_columns,
        var_name="tanggal_sumber",
        value_name="harga_sumber",
    )
    long["tanggal"] = pd.to_datetime(
        long["tanggal_sumber"], format=fmt["date_format"], errors="coerce"
    )

    harga_text = long["harga_sumber"].str.strip()
    if fmt["thousands_separator"]:
        harga_text = harga_text.str.replace(
            fmt["thousands_separator"], "", regex=False
        )
    long["harga"] = pd.to_numeric(harga_text, errors="coerce")

    # Baris valid: identitas lengkap, tanggal valid, harga > 0
    valid = (
        (long[ID_COLUMNS] != "").all(axis=1)
        & long["tanggal"].notna()
        & (long["harga"] > 0)
    )
    cleaned = long.loc[valid, ID_COLUMNS + ["tanggal", "harga"]].copy()

    before = len(cleaned)
    cleaned = cleaned.drop_duplicates(
        subset=REGION_KEY + ["komoditas", "tanggal"], keep="last"
    )
    duplicates = before - len(cleaned)

    # Samakan nama komoditas (mis. CABAI MERAH BESAR -> CABAI MERAH)
    cleaned["komoditas"] = cleaned["komoditas"].replace(COMMODITY_MAPPING)

    # Ringkas harian -> bulanan. Simpan JUMLAH dan BANYAK data (bukan rata-rata)
    # supaya bisa digabung dengan benar antar-file.
    cleaned["periode"] = cleaned["tanggal"].dt.strftime("%Y-%m")
    monthly = cleaned.groupby(
        REGION_KEY + ["komoditas", "periode"], as_index=False
    ).agg(harga_total=("harga", "sum"), n_obs=("harga", "count"))

    # Kode daerah hanya disimpan sebagai informasi (versi terbaru menang)
    names = cleaned[REGION_KEY + ["kode_daerah"]].drop_duplicates(
        REGION_KEY, keep="last"
    )

    quality = {
        "file": path.name,
        "baris_kandidat": int(len(long)),
        "baris_diterima": int(before),
        "baris_ditolak": int(len(long) - before),
        "duplikat_dihapus": int(duplicates),
    }
    return monthly, names, quality


def build_monthly_prices():
    """Jalankan pembersihan untuk semua file lalu simpan CSV bulanan."""
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)

    monthly_parts, name_parts, quality_rows = [], [], []
    for file_name in RAW_FILES:
        monthly, names, quality = clean_one_file(RAW_DIR / file_name)
        monthly_parts.append(monthly)
        name_parts.append(names)
        quality_rows.append(quality)
        print(f"[ETL] {file_name}: {quality['baris_diterima']:,} baris diterima")

    # Gabung semua file, jumlahkan lagi per wilayah-komoditas-bulan
    monthly = (
        pd.concat(monthly_parts, ignore_index=True)
        .groupby(REGION_KEY + ["komoditas", "periode"], as_index=False)
        .agg(harga_total=("harga_total", "sum"), n_obs=("n_obs", "sum"))
    )
    monthly["harga_rata2"] = monthly["harga_total"] / monthly["n_obs"]

    # Kode daerah: pakai yang terbaru (file terakhir = data-2026 menang)
    names = pd.concat(name_parts, ignore_index=True).drop_duplicates(
        REGION_KEY, keep="last"
    )
    names["kode_provinsi"] = names["kode_daerah"].str[:2]  # 1101 -> 11 (Aceh)

    result = monthly.merge(names, on=REGION_KEY, how="left")
    result = result[
        ["kode_provinsi", "provinsi", "kode_daerah", "kabupaten_kota",
         "komoditas", "periode", "harga_rata2", "n_obs"]
    ].sort_values(["periode", "komoditas", "provinsi", "kabupaten_kota"])

    result.to_csv(MONTHLY_PRICES_CSV, index=False, encoding="utf-8")

    return {
        "file_hasil": str(MONTHLY_PRICES_CSV),
        "baris": int(len(result)),
        "periode": sorted(result["periode"].unique().tolist()),
        "jumlah_kabupaten_kota": int(len(result[REGION_KEY].drop_duplicates())),
        "jumlah_provinsi": int(result["provinsi"].nunique()),
        "jumlah_komoditas": int(result["komoditas"].nunique()),
        "baris_ditolak_total": int(sum(q["baris_ditolak"] for q in quality_rows)),
    }
