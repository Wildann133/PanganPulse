# Panduan Fitur Regional Comparison — PanganPulse

Panduan ini membawamu dari laptop kosong sampai fitur **Regional Comparison** jalan: perhitungan selisih harga, peringkat, dan Coefficient of Variation (CV), plus orkestrasi ETL dengan Airflow. Semua kode sudah diuji pada data repo kelompokmu.

> Cara membaca: kerjakan **berurutan**. Tiap bagian punya **"Kamu berhasil kalau..."**. Kalau hasilnya beda, berhenti dan lihat Bagian 10 (Masalah umum) sebelum lanjut.
> Perintah terminal ditulis untuk **Windows + PowerShell** (terminal bawaan VS Code).

---

## Bagian 0 — Gambaran besar

Empat tugasmu dan di mana masing-masing dikerjakan:

| Tugas | Isinya | Dikerjakan di |
|---|---|---|
| 1. Implementasi regional comparison | Halaman web `/perbandingan-wilayah/` | Bagian 6 (Django) |
| 2. Bandingkan harga komoditas antarwilayah | Filter komoditas + periode + level wilayah, tabel dan grafik | Bagian 6 |
| 3. Selisih harga, ranking, CV | Perhitungan di Python (pandas) | Bagian 4 (`regional_metrics.py`) |
| 4. Airflow untuk orkestrasi ETL | DAG 5 langkah + Docker | Bagian 5 |

Alur datanya:

```
CSV mentah  etl/data/dataset/*.csv
   |  Airflow task 1-2: cek file, bersihkan, ringkas jadi rata-rata BULANAN
   v
etl/data/processed/regional_monthly_prices.csv
   |  Airflow task 3: hitung selisih, peringkat, CV
   v
regional_comparison_prices.csv  +  regional_comparison_summary.csv
   |  Airflow task 4-5: muat ke MongoDB lalu validasi jumlah dokumen
   v
MongoDB  (database pangan_pulse)
   |  pymongo
   v
Django  ->  halaman /perbandingan-wilayah/  (tabel + grafik Plotly)
```

### Istilah yang dipakai (hafalkan ini, dosen pasti tanya)

| Istilah | Arti di proyek ini |
|---|---|
| **Wilayah** | Satu provinsi (38) atau satu kabupaten/kota (514), tergantung pilihan *level*. |
| **Harga rata-rata wilayah** | Rata-rata harga satu komoditas di satu wilayah selama satu bulan. Harga provinsi = rata-rata harga kab/kota di dalamnya (tiap kab/kota bobotnya sama). |
| **Selisih vs rata-rata** | Harga wilayah dikurangi rata-rata semua wilayah (Rp dan %). Positif = lebih mahal dari rata-rata. |
| **Selisih vs termurah** | Harga wilayah dikurangi harga wilayah termurah (selalu 0 atau lebih). |
| **Peringkat** | 1 = paling mahal. Harga sama = peringkat sama. |
| **CV (Coefficient of Variation)** | simpangan baku harga antarwilayah ÷ rata-rata × 100%. Makin besar, makin timpang harga antarwilayah. |

### Temuan di data timmu (penting, sudah ditangani di kode)

1. **Kode daerah 2025 dan 2026 berbeda untuk wilayah yang sama.** Contoh: Kota Dumai kodenya 1473 di 2025 tapi 1472 di 2026; kode provinsi Papua juga bergeser. Kalau dipakai sebagai kunci, wilayah akan terhitung ganda (544 kab/kota, bukan 514). Kode ini **tidak** dipakai sebagai kunci; kuncinya adalah **nama provinsi + nama kab/kota** (setelah menyeragamkan penulisan `Kab` / `Kab.`). Hasilnya 514 kab/kota dan 38 provinsi, tepat.
2. **Data 2026 baru sampai 13 November 2026**, jadi periode `2026-11` hanya setengah bulan.
3. **Beberapa komoditas hanya ada di satu tahun** (misalnya `JERUK` hanya 2025, `MINYAKITA` hanya 2026). Di halaman, kombinasi seperti itu menampilkan pesan "Tidak ada data".
4. **Ambang kategori CV (Rendah < 15%, Sedang 15–30%, Tinggi ≥ 30%) adalah pilihan**, bukan standar baku. Angkanya kupilih dari sebaran CV data ini supaya ketiga kategori terisi. Kalau kelompok punya acuan lain, ubah `CV_LOW_MAX` dan `CV_MEDIUM_MAX` di `config.py`.

---

## Bagian 1 — Instal alat (sekali saja)

Lewati yang sudah terpasang. Cek dulu di PowerShell: `git --version`, `python --version`, `docker --version`.

**1. Git**
1. Buka https://git-scm.com/download/win, unduh, jalankan installer.
2. Klik **Next** terus sampai **Install** (pengaturan bawaan sudah cukup), lalu **Finish**.

**2. Python 3.12**
1. Buka https://www.python.org/downloads/ lalu klik tombol **Download Python 3.12.x** (versi 3.11 atau lebih baru boleh).
2. Jalankan installer. **Centang "Add python.exe to PATH"** (kotak di bagian bawah), lalu klik **Install Now**.

**3. VS Code + ekstensi Python**
1. Buka VS Code, klik ikon **Extensions** di sisi kiri (atau `Ctrl+Shift+X`).
2. Ketik `Python`, pilih yang dari **Microsoft**, klik **Install**.

**4. Docker Desktop** (dibutuhkan untuk Airflow)
1. Buka https://www.docker.com/products/docker-desktop/ lalu klik **Download for Windows**.
2. Jalankan installer, biarkan **"Use WSL 2 instead of Hyper-V"** tercentang, klik **OK**, tunggu selesai, klik **Close and restart**.
3. Setelah laptop menyala, buka **Docker Desktop**, klik **Accept** pada persetujuan, lewati login (pilih **Skip** atau **Continue without signing in**).
4. Tunggu sampai di kiri bawah jendela tertulis **"Engine running"** (warna hijau). Docker harus dalam keadaan ini setiap kali kamu mengerjakan Bagian 5.

**5. (Opsional) MongoDB Compass** untuk melihat isi database secara visual: https://www.mongodb.com/products/tools/compass

---

## Bagian 2 — Ambil repo dan buat branch

Jangan kerja langsung di `main`. Buat branch sendiri supaya pekerjaanmu tidak bentrok dengan teman.

1. Buka VS Code. Tekan `Ctrl+Shift+P`, ketik `Git: Clone`, tekan Enter.
2. Tempel URL repo: `https://github.com/Wildann133/PanganPulse.git` (kalau URL-mu beda, ambil dari tombol hijau **Code** di halaman GitHub repo).
3. Pilih folder tujuan (misalnya `Documents`), lalu klik **Select as Repository Destination**. Kalau muncul jendela login GitHub, klik **Allow** / **Sign in with browser**.
4. Klik **Open** pada notifikasi "Would you like to open the cloned repository?".
5. Klik tulisan **main** di pojok kiri bawah VS Code, pilih **Create new branch...**, ketik `feature/regional-comparison`, tekan Enter.
6. Buka terminal: tekan `` Ctrl+` `` (tombol backtick, di atas Tab).

**Kamu berhasil kalau** terminal menampilkan `PS ...\PanganPulse>` dan kiri bawah VS Code bertuliskan `feature/regional-comparison`.

> Kalau muncul *permission denied* saat nanti push, minta pemilik repo (Wildann133) menambahkanmu lewat GitHub: **Settings → Collaborators → Add people**.

---

## Bagian 3 — Siapkan Python (virtual environment)

Di terminal VS Code, dari folder utama `PanganPulse`:

```powershell
python -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt
pip install mongomock
```

- Kalau `Activate.ps1` ditolak ("running scripts is disabled"), jalankan sekali: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`, jawab `Y`, lalu ulangi baris Activate.
- Setelah aktif, awal baris terminal berubah menjadi `(.venv)`.
- Pilih interpreter di VS Code: `Ctrl+Shift+P` → `Python: Select Interpreter` → pilih yang ada tulisan `.venv`.
- `pip install` pertama kali butuh beberapa menit.

Cek bahwa Django dasar sehat:

```powershell
cd backend
python manage.py check
cd ..
```

**Kamu berhasil kalau** muncul `System check identified no issues (0 silenced).`

---

## Bagian 4 — ETL dan perhitungan metrik (tugas 3)

Kita buat paket Python baru `etl/pangan_etl/`. Isinya meniru logika pembersihan di `ETL.ipynb` milik timmu, tapi dalam bentuk file `.py` supaya Airflow bisa menjalankannya otomatis.

> **Jalan pintas:** semua file di panduan ini juga ada di `regional-comparison-files.zip`. Kamu boleh ekstrak zip itu ke folder utama repo (pilih *Replace* bila ditanya), lalu lompat ke bagian **"Jalankan"**. Tapi sebaiknya buat satu per satu dulu supaya paham.

**Cara membuat file di VS Code:** klik kanan folder di panel **Explorer** (kiri) → **New Folder** / **New File** → ketik nama → Enter → tempel kode → `Ctrl+S`.

Buat struktur ini di dalam folder `etl`:

```
etl/
  pangan_etl/
    __init__.py            (kosong, cukup dibuat)
    config.py
    extract_transform.py
    regional_metrics.py
    load_mongo.py
    run_pipeline.py
  tests/
    __init__.py            (kosong)
    test_regional_metrics.py
    test_load_mongo.py
```

### 4.1 `etl/pangan_etl/config.py`
Satu tempat untuk semua pengaturan (lokasi folder, format file mentah, mapping komoditas, ambang CV, alamat MongoDB).

```python
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
```

### 4.2 `etl/pangan_etl/extract_transform.py`
Membaca 13 CSV mentah, membersihkan, menyeragamkan nama komoditas, lalu meringkas jadi rata-rata harga **bulanan** per kab/kota.

```python
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
```

### 4.3 `etl/pangan_etl/regional_metrics.py`
Inti tugasmu: selisih harga, peringkat, dan CV.

```python
"""
Tahap TRANSFORM lanjutan: menghitung metrik Regional Comparison.

Untuk setiap kombinasi (level, periode, komoditas) dihitung:
  - selisih harga tiap wilayah terhadap rata-rata antarwilayah (Rp dan %)
  - selisih harga terhadap wilayah termurah (Rp)
  - peringkat (1 = harga paling mahal)
  - Coefficient of Variation (CV) = simpangan baku / rata-rata x 100%
  - ringkasan: termurah, termahal, selisih maks-min, disparitas %

level:
  - "kabupaten_kota" : 1 wilayah = 1 kabupaten/kota (sekitar 514)
  - "provinsi"       : 1 wilayah = 1 provinsi (38). Harga provinsi = rata-rata
                       harga kabupaten/kota di dalamnya (tiap kab/kota bobot sama).
"""
import pandas as pd

from .config import (
    COMPARISON_PRICES_CSV,
    COMPARISON_SUMMARY_CSV,
    CV_LOW_MAX,
    CV_MEDIUM_MAX,
    MONTHLY_PRICES_CSV,
)

KEYS = ["level", "periode", "komoditas"]
LEVELS = ["provinsi", "kabupaten_kota"]


def build_region_prices(monthly, level):
    """Ubah harga bulanan per kab/kota menjadi harga per 'wilayah' sesuai level."""
    if level == "kabupaten_kota":
        out = monthly.rename(
            columns={"kode_daerah": "kode_wilayah", "kabupaten_kota": "nama_wilayah"}
        )[["periode", "komoditas", "kode_wilayah", "nama_wilayah",
           "provinsi", "harga_rata2", "n_obs"]].copy()
        out["jumlah_kabkota"] = 1
    elif level == "provinsi":
        out = (
            monthly.groupby(
                ["periode", "komoditas", "kode_provinsi", "provinsi"], as_index=False
            )
            .agg(
                harga_rata2=("harga_rata2", "mean"),
                n_obs=("n_obs", "sum"),
                jumlah_kabkota=("kabupaten_kota", "nunique"),
            )
            .rename(columns={"kode_provinsi": "kode_wilayah"})
        )
        out["nama_wilayah"] = out["provinsi"]
    else:
        raise ValueError(f"level tidak dikenal: {level}")

    out.insert(0, "level", level)
    return out.reset_index(drop=True)


def classify_cv(cv):
    """Kategori disparitas dari nilai CV (%)."""
    if pd.isna(cv):
        return None
    if cv < CV_LOW_MAX:
        return "Rendah"
    if cv < CV_MEDIUM_MAX:
        return "Sedang"
    return "Tinggi"


def add_price_gaps_and_rank(prices):
    """Tambahkan selisih harga dan peringkat ke tabel harga wilayah."""
    df = prices.copy()
    grp = df.groupby(KEYS)["harga_rata2"]

    df["total_wilayah"] = grp.transform("count")
    df["rata2_antarwilayah"] = grp.transform("mean")
    df["harga_termurah"] = grp.transform("min")

    # selisih terhadap rata-rata antarwilayah
    df["selisih_rp"] = df["harga_rata2"] - df["rata2_antarwilayah"]
    df["selisih_persen"] = df["selisih_rp"] / df["rata2_antarwilayah"] * 100
    # selisih terhadap wilayah termurah (selalu >= 0)
    df["selisih_vs_termurah_rp"] = df["harga_rata2"] - df["harga_termurah"]

    # peringkat: 1 = termahal; harga sama -> peringkat sama
    df["peringkat"] = grp.rank(method="min", ascending=False).astype(int)

    df = df.drop(columns=["harga_termurah"])
    return df


def build_summary(prices):
    """Ringkasan per (level, periode, komoditas), termasuk CV."""
    grp = prices.groupby(KEYS)
    summary = grp["harga_rata2"].agg(
        n_wilayah="count",
        harga_rata2="mean",
        harga_median="median",
        harga_std="std",       # simpangan baku sampel (ddof=1)
        harga_min="min",
        harga_max="max",
    )

    # nama wilayah termurah & termahal
    idx_min = grp["harga_rata2"].idxmin()
    idx_max = grp["harga_rata2"].idxmax()
    summary["wilayah_termurah"] = (
        prices.loc[idx_min, KEYS + ["nama_wilayah"]].set_index(KEYS)["nama_wilayah"]
    )
    summary["wilayah_termahal"] = (
        prices.loc[idx_max, KEYS + ["nama_wilayah"]].set_index(KEYS)["nama_wilayah"]
    )

    summary["selisih_max_min_rp"] = summary["harga_max"] - summary["harga_min"]
    summary["disparitas_persen"] = (
        summary["selisih_max_min_rp"] / summary["harga_min"] * 100
    )
    # CV: kalau wilayah < 2, simpangan baku NaN -> CV NaN
    summary["cv_persen"] = summary["harga_std"] / summary["harga_rata2"] * 100
    summary["kategori_disparitas"] = summary["cv_persen"].apply(classify_cv)

    return summary.reset_index()


def compute_regional_comparison(monthly):
    """Hitung tabel harga+peringkat dan tabel ringkasan untuk semua level."""
    price_parts = []
    for level in LEVELS:
        region_prices = build_region_prices(monthly, level)
        price_parts.append(add_price_gaps_and_rank(region_prices))
    prices = pd.concat(price_parts, ignore_index=True)
    summary = build_summary(prices)

    money_cols = [
        "harga_rata2", "rata2_antarwilayah", "selisih_rp", "selisih_vs_termurah_rp",
    ]
    prices[money_cols] = prices[money_cols].round(2)
    prices["selisih_persen"] = prices["selisih_persen"].round(2)
    summary = summary.round(2)
    return prices, summary


def run_compute_metrics():
    """Baca CSV bulanan, hitung metrik, simpan dua CSV hasil."""
    monthly = pd.read_csv(
        MONTHLY_PRICES_CSV,
        dtype={"kode_provinsi": "string", "kode_daerah": "string"},
    )
    prices, summary = compute_regional_comparison(monthly)

    prices.to_csv(COMPARISON_PRICES_CSV, index=False, encoding="utf-8")
    summary.to_csv(COMPARISON_SUMMARY_CSV, index=False, encoding="utf-8")

    return {
        "baris_harga": int(len(prices)),
        "baris_ringkasan": int(len(summary)),
        "file_harga": str(COMPARISON_PRICES_CSV),
        "file_ringkasan": str(COMPARISON_SUMMARY_CSV),
    }
```

### 4.4 `etl/pangan_etl/load_mongo.py`
Memasukkan hasil ke MongoDB (hapus isi lama lalu isi ulang, jadi aman dijalankan berkali-kali).

```python
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
```

### 4.5 `etl/pangan_etl/run_pipeline.py`
Menjalankan semua tahap lewat satu perintah (tanpa Airflow), berguna untuk uji coba.

```python
"""
Menjalankan seluruh pipeline Regional Comparison dari terminal (tanpa Airflow).

Cara pakai (dari folder etl/):
    python -m pangan_etl.run_pipeline              # semua tahap sampai MongoDB
    python -m pangan_etl.run_pipeline --skip-load  # berhenti sebelum MongoDB
"""
import argparse

from .extract_transform import build_monthly_prices, check_raw_files
from .load_mongo import run_load, validate_load
from .regional_metrics import run_compute_metrics


def main():
    parser = argparse.ArgumentParser(description="Pipeline Regional Comparison")
    parser.add_argument("--skip-load", action="store_true",
                        help="jangan muat ke MongoDB (hanya hasilkan CSV)")
    args = parser.parse_args()

    print("1/5 Cek file mentah ...", check_raw_files())
    print("2/5 Bersihkan & ringkas bulanan ...", build_monthly_prices())
    print("3/5 Hitung metrik ...", run_compute_metrics())
    if args.skip_load:
        print("Selesai (MongoDB dilewati).")
        return
    print("4/5 Muat ke MongoDB ...", run_load())
    print("5/5 Validasi ...", validate_load())
    print("Selesai.")


if __name__ == "__main__":
    main()
```

### 4.6 Tes otomatis

`etl/tests/test_regional_metrics.py` (memeriksa rumus dengan angka kecil yang bisa dihitung di kepala):

```python
"""
Unit test untuk perhitungan Regional Comparison.

Jalankan dari folder etl/:
    python -m unittest discover -s tests -v
"""
import unittest

import pandas as pd

from pangan_etl.regional_metrics import (
    classify_cv,
    compute_regional_comparison,
)


def sample_monthly():
    """Data kecil: 1 komoditas, 1 periode, 3 kab/kota di 2 provinsi."""
    return pd.DataFrame({
        "kode_provinsi": ["11", "11", "12"],
        "provinsi": ["Aceh", "Aceh", "Sumut"],
        "kode_daerah": ["1101", "1102", "1201"],
        "kabupaten_kota": ["Kab. A", "Kab. B", "Kab. C"],
        "komoditas": ["BERAS MEDIUM"] * 3,
        "periode": ["2026-01"] * 3,
        "harga_rata2": [10000.0, 12000.0, 14000.0],
        "n_obs": [10, 10, 10],
    })


class RegionalMetricsTest(unittest.TestCase):
    def setUp(self):
        self.prices, self.summary = compute_regional_comparison(sample_monthly())

    def kab(self, nama):
        df = self.prices
        return df[(df.level == "kabupaten_kota") & (df.nama_wilayah == nama)].iloc[0]

    def test_selisih_terhadap_rata_rata(self):
        # rata-rata = 12000
        self.assertEqual(self.kab("Kab. A").selisih_rp, -2000)
        self.assertEqual(self.kab("Kab. C").selisih_rp, 2000)
        self.assertAlmostEqual(self.kab("Kab. C").selisih_persen, 16.67, places=2)

    def test_selisih_terhadap_termurah(self):
        self.assertEqual(self.kab("Kab. A").selisih_vs_termurah_rp, 0)
        self.assertEqual(self.kab("Kab. C").selisih_vs_termurah_rp, 4000)

    def test_peringkat_satu_adalah_termahal(self):
        self.assertEqual(self.kab("Kab. C").peringkat, 1)
        self.assertEqual(self.kab("Kab. B").peringkat, 2)
        self.assertEqual(self.kab("Kab. A").peringkat, 3)

    def test_cv_kabupaten(self):
        # std sampel [10000,12000,14000] = 2000 ; CV = 2000/12000*100
        row = self.summary[self.summary.level == "kabupaten_kota"].iloc[0]
        self.assertAlmostEqual(row.cv_persen, 16.67, places=2)
        self.assertEqual(row.kategori_disparitas, "Sedang")
        self.assertEqual(row.wilayah_termurah, "Kab. A")
        self.assertEqual(row.wilayah_termahal, "Kab. C")
        self.assertEqual(row.selisih_max_min_rp, 4000)

    def test_level_provinsi_memakai_rata_rata_kabkota(self):
        prov = self.prices[self.prices.level == "provinsi"].set_index("nama_wilayah")
        self.assertEqual(prov.loc["Aceh", "harga_rata2"], 11000)  # (10000+12000)/2
        self.assertEqual(prov.loc["Aceh", "jumlah_kabkota"], 2)
        self.assertEqual(prov.loc["Sumut", "peringkat"], 1)

    def test_satu_wilayah_cv_kosong(self):
        one = sample_monthly().iloc[:1]
        _, summary = compute_regional_comparison(one)
        self.assertTrue(summary["cv_persen"].isna().all())

    def test_classify_cv(self):
        self.assertEqual(classify_cv(5), "Rendah")
        self.assertEqual(classify_cv(20), "Sedang")
        self.assertEqual(classify_cv(45), "Tinggi")
        self.assertIsNone(classify_cv(float("nan")))


if __name__ == "__main__":
    unittest.main()
```

`etl/tests/test_load_mongo.py` (memeriksa tahap muat dengan MongoDB palsu, tanpa server):

```python
"""
Test tahap LOAD memakai MongoDB palsu (mongomock) - tidak perlu server Mongo.
Instal dulu:  pip install mongomock
"""
import unittest

import bson
import mongomock

from pangan_etl import load_mongo
from pangan_etl.regional_metrics import compute_regional_comparison
from tests.test_regional_metrics import sample_monthly


class LoadMongoTest(unittest.TestCase):
    def test_records_valid_untuk_bson_dan_nan_jadi_none(self):
        prices, summary = compute_regional_comparison(sample_monthly().iloc[:1])
        for df in (prices, summary):
            for rec in load_mongo._to_records(df):
                bson.encode(rec)  # error jika ada tipe numpy / NaN yang tidak valid
        rec = load_mongo._to_records(summary)[0]
        self.assertIsNone(rec["cv_persen"])

    def test_replace_collection_tidak_menggandakan_data(self):
        prices, _ = compute_regional_comparison(sample_monthly())
        col = mongomock.MongoClient().db.coll
        load_mongo._replace_collection(col, prices)
        load_mongo._replace_collection(col, prices)  # dijalankan dua kali
        self.assertEqual(col.count_documents({}), len(prices))


if __name__ == "__main__":
    unittest.main()
```

### 4.7 Tambahkan dua baris ke file bersama

Buka `etl/requirements.txt` dan tambahkan di baris paling bawah:

```
pymongo
mongomock
```

Buka `.gitignore` (di folder utama) dan tambahkan di paling bawah, supaya file hasil olahan yang besar tidak ikut di-commit:

```
etl/data/processed/regional_monthly_prices.csv
etl/data/processed/regional_comparison_prices.csv
etl/data/processed/regional_comparison_summary.csv
```

### Jalankan

```powershell
cd etl
python -m unittest discover -s tests -v
python -m pangan_etl.run_pipeline --skip-load
```

**Kamu berhasil kalau:**
- Tes: tertulis `Ran 9 tests ... OK`.
- Pipeline (sekitar 1 menit): tampil 13 baris `[ETL] ... baris diterima`, lalu ringkasan berisi `jumlah_kabupaten_kota: 514`, `jumlah_provinsi: 38`, `jumlah_komoditas: 32`, 23 periode (`2025-01` s.d. `2026-11`), dan `baris_harga: 254854`, `baris_ringkasan: 1022`. Tiga file baru `regional_*.csv` muncul di `etl/data/processed/`.

> Salah satu file hasil, `regional_comparison_summary.csv`, ringan dan enak dibuka di Excel/VS Code untuk memeriksa angka.

---

## Bagian 5 — Airflow dan Docker (tugas 4)

Airflow adalah "manajer" yang menjalankan langkah-langkah ETL **berurutan**, mencoba ulang kalau gagal, dan menampilkan statusnya di web. Satu rangkaian langkah disebut **DAG**. Docker dipakai karena Airflow tidak berjalan langsung di Windows.

Buat tiga file:

### 5.1 `airflow/dags/regional_comparison_dag.py`
(Hapus `.gitkeep` di folder itu kalau mau rapi; tidak wajib.)

```python
"""
DAG Airflow: pipeline ETL fitur Regional Comparison.

  cek_file_mentah -> bersihkan_ringkas_bulanan -> hitung_metrik
                  -> muat_ke_mongodb -> validasi_data

Setiap task hanya memanggil fungsi di etl/pangan_etl/, jadi logika yang sama
juga bisa dijalankan manual lewat terminal (python -m pangan_etl.run_pipeline).
"""
from datetime import datetime, timedelta

from airflow.decorators import dag, task


@dag(
    dag_id="panganpulse_regional_comparison",
    description="ETL harga pangan -> metrik perbandingan antarwilayah -> MongoDB",
    start_date=datetime(2026, 11, 1),
    schedule="@weekly",   # data sumber diperbarui berkala; bisa juga dipicu manual
    catchup=False,
    max_active_runs=1,
    default_args={
        "owner": "panganpulse",
        "retries": 1,
        "retry_delay": timedelta(minutes=2),
    },
    tags=["panganpulse", "regional-comparison", "etl"],
)
def regional_comparison_pipeline():

    @task
    def cek_file_mentah():
        from pangan_etl.extract_transform import check_raw_files
        return check_raw_files()

    @task
    def bersihkan_ringkas_bulanan(_cek):
        from pangan_etl.extract_transform import build_monthly_prices
        return build_monthly_prices()

    @task
    def hitung_metrik(_etl):
        from pangan_etl.regional_metrics import run_compute_metrics
        return run_compute_metrics()

    @task
    def muat_ke_mongodb(_metrik):
        from pangan_etl.load_mongo import run_load
        return run_load()

    @task
    def validasi_data(_muat):
        from pangan_etl.load_mongo import validate_load
        return validate_load()

    # Urutan eksekusi: tiap task menunggu hasil task sebelumnya
    validasi_data(
        muat_ke_mongodb(
            hitung_metrik(
                bersihkan_ringkas_bulanan(
                    cek_file_mentah()
                )
            )
        )
    )


regional_comparison_pipeline()
```

### 5.2 `docker/Dockerfile.airflow`

```dockerfile
# Image Airflow + library yang dibutuhkan pipeline PanganPulse
FROM apache/airflow:2.10.5-python3.11

RUN pip install --no-cache-dir pandas pymongo
```

### 5.3 `docker/docker-compose.airflow.yml`
Isinya dua "kontainer": **mongo** (database, dibuka di port **27018** di laptopmu supaya tidak bentrok dengan MongoDB lokal di 27017) dan **airflow** (web di port 8080).

```yaml
# Menjalankan Airflow + MongoDB untuk pipeline PanganPulse.
# Jalankan dari folder docker/:   docker compose -f docker-compose.airflow.yml up -d --build
name: panganpulse

services:
  mongo:
    image: mongo:7
    container_name: panganpulse-mongo
    ports:
      - "27018:27017"   # port 27018 di laptop -> 27017 di container (hindari bentrok dengan MongoDB lokal)
    volumes:
      - mongo_data:/data/db
    restart: unless-stopped

  airflow:
    build:
      context: .
      dockerfile: Dockerfile.airflow
    container_name: panganpulse-airflow
    depends_on:
      - mongo
    ports:
      - "8080:8080"
    environment:
      AIRFLOW__CORE__LOAD_EXAMPLES: "false"
      AIRFLOW__DATABASE__SQL_ALCHEMY_CONN: "sqlite:////opt/airflow/db/airflow.db"
      PYTHONPATH: /opt/airflow/etl          # agar DAG bisa 'import pangan_etl'
      MONGO_URI: mongodb://mongo:27017      # di dalam Docker, MongoDB dipanggil lewat nama service
      MONGO_DB_NAME: pangan_pulse
    volumes:
      - ../airflow/dags:/opt/airflow/dags
      - ../etl:/opt/airflow/etl
      - airflow_db:/opt/airflow/db
    command:
      - bash
      - -c
      - |
        airflow db migrate
        airflow users create --username admin --password admin --firstname Admin --lastname PanganPulse --role Admin --email admin@example.com || true
        airflow scheduler &
        exec airflow webserver --port 8080
    restart: unless-stopped

volumes:
  mongo_data:
  airflow_db:
```

### Jalankan Airflow

1. Pastikan **Docker Desktop terbuka** dan tertulis *Engine running*.
2. Di terminal VS Code (dari folder utama):
   ```powershell
   cd docker
   docker compose -f docker-compose.airflow.yml up -d --build
   ```
   Pertama kali butuh 3–8 menit (mengunduh image). Tunggu sampai kembali ke prompt.
3. Tunggu sekitar 1 menit, lalu buka http://localhost:8080 di browser.
4. Login: username `admin`, password `admin` (khusus pengembangan lokal).
5. Di daftar DAG, cari **`panganpulse_regional_comparison`**. (Kalau belum muncul, tunggu 30 detik lalu refresh.)
6. Klik **geser tombol** di sisi kiri nama DAG sampai berwarna biru (itu *unpause*). Airflow mungkin langsung menjalankannya sekali.
7. Untuk menjalankan manual: klik nama DAG → klik tombol **▶ (Trigger DAG)** di pojok kanan atas → **Trigger**.
8. Klik tab **Grid**. Lima kotak harus berubah hijau berurutan: `cek_file_mentah` → `bersihkan_ringkas_bulanan` → `hitung_metrik` → `muat_ke_mongodb` → `validasi_data`. Untuk melihat log sebuah langkah: klik kotaknya → **Logs**.

Langkah `bersihkan_ringkas_bulanan` paling lama (1–5 menit di Docker).

**Kamu berhasil kalau** kelima kotak hijau. Periksa isi database:

```powershell
docker exec -it panganpulse-mongo mongosh
```
lalu di dalam `mongosh`:
```js
use pangan_pulse
db.regional_comparison_summary.countDocuments()   // 1022
db.regional_comparison_prices.countDocuments()    // 254854
exit
```
(Angka mengikuti data repo saat panduan ini dibuat; kalau tim menambah data, angkanya bisa berbeda. Yang penting keduanya lebih dari 0 dan task `validasi_data` hijau.)

Menghentikan: `docker compose -f docker-compose.airflow.yml down` (data tetap tersimpan). Menyalakan lagi: `docker compose -f docker-compose.airflow.yml up -d`.

---

## Bagian 6 — Halaman Django (tugas 1 dan 2)

Django membaca hasil dari MongoDB. App `regional_comparison` sudah ada (dibuat timmu), kita isi.

### 6.1 Edit dua file bersama (edit kecil, jangan ditimpa)

**`backend/config/settings.py`** — dua perubahan:

(a) Di bagian paling atas, tambahkan `import os` di atas `from pathlib import Path`:

```python
import os
from pathlib import Path
```

(b) Di paling bawah file, tambahkan:

```python
# MongoDB (data hasil pipeline ETL / Airflow)
# Port 27018 = MongoDB milik docker-compose proyek (lihat docker/docker-compose.airflow.yml)
MONGO_URI = os.environ.get('MONGO_URI', 'mongodb://localhost:27018')
MONGO_DB_NAME = os.environ.get('MONGO_DB_NAME', 'pangan_pulse')
MONGO_COLLECTION_PRICES = 'regional_comparison_prices'
MONGO_COLLECTION_SUMMARY = 'regional_comparison_summary'
```

**`backend/config/urls.py`** — ubah menjadi:

```python
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path('admin/', admin.site.urls),
    path('perbandingan-wilayah/', include('apps.regional_comparison.urls')),
]
```
(Kalau temanmu sudah menambah baris `path(...)` lain di file ini, **pertahankan baris mereka**, cukup tambahkan `include` pada import dan satu baris `path('perbandingan-wilayah/', ...)`.)

### 6.2 File baru/isi baru di `backend/apps/regional_comparison/`

Buat `templatetags/__init__.py` (kosong) dan file-file berikut. `views.py` dan `tests.py` sudah ada berisi contoh bawaan Django; **ganti seluruh isinya**.

**`services.py`** (semua query MongoDB ada di sini):

```python
"""
Lapisan akses data Regional Comparison.

View tidak langsung bicara ke MongoDB; semua query ada di sini supaya mudah
dites dan diganti. Data berasal dari koleksi yang diisi pipeline ETL/Airflow.
"""
from django.conf import settings
from pymongo import MongoClient

LEVELS = {"provinsi": "Provinsi", "kabupaten_kota": "Kabupaten/Kota"}

_client = None


def get_db():
    """Koneksi MongoDB (dibuat sekali lalu dipakai ulang)."""
    global _client
    if _client is None:
        _client = MongoClient(settings.MONGO_URI, serverSelectionTimeoutMS=3000)
    return _client[settings.MONGO_DB_NAME]


def _prices():
    return get_db()[settings.MONGO_COLLECTION_PRICES]


def _summary():
    return get_db()[settings.MONGO_COLLECTION_SUMMARY]


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
```

**`urls.py`**:

```python
from django.urls import path

from . import views

app_name = "regional_comparison"

urlpatterns = [
    path("", views.index, name="index"),
]
```

**`views.py`** (ganti seluruh isi):

```python
from django.shortcuts import render
from pymongo.errors import PyMongoError

from . import services


def index(request):
    """Halaman Perbandingan Harga Antarwilayah."""
    context = {"levels": services.LEVELS}

    try:
        periods = services.list_periods()
        commodities = services.list_commodities()
    except PyMongoError:
        context["error"] = (
            "Tidak dapat terhubung ke MongoDB. Pastikan container MongoDB "
            "berjalan dan pipeline Airflow sudah dijalankan."
        )
        return render(request, "regional_comparison/index.html", context)

    if not periods or not commodities:
        context["error"] = (
            "Data belum tersedia. Jalankan DAG "
            "'panganpulse_regional_comparison' di Airflow terlebih dahulu."
        )
        return render(request, "regional_comparison/index.html", context)

    # Ambil pilihan dari URL (?level=...&periode=...&komoditas=...), pakai default jika kosong/salah
    level = services.normalize_level(request.GET.get("level"))
    periode = request.GET.get("periode")
    if periode not in periods:
        periode = periods[0]
    komoditas = request.GET.get("komoditas")
    if komoditas not in commodities:
        komoditas = "BERAS MEDIUM" if "BERAS MEDIUM" in commodities else commodities[0]

    ranking = services.get_ranking(level, periode, komoditas)
    cv_ranking = services.get_cv_ranking(level, periode)

    # Grafik dengan ratusan batang tidak terbaca: untuk level kab/kota tampilkan
    # 15 termahal + 15 termurah saja (tabel di bawah tetap memuat semuanya).
    chart_rows = ranking
    chart_note = ""
    if len(ranking) > 40:
        chart_rows = ranking[:15] + ranking[-15:]
        chart_note = "Grafik menampilkan 15 wilayah termahal dan 15 termurah."

    context.update({
        "periods": periods,
        "commodities": commodities,
        "level": level,
        "level_label": services.LEVELS[level],
        "periode": periode,
        "komoditas": komoditas,
        "summary": services.get_summary(level, periode, komoditas),
        "ranking": ranking,
        "cv_ranking": cv_ranking,
        # data untuk grafik Plotly (dibaca lewat json_script di template)
        "chart_note": chart_note,
        "chart_ranking": [
            {"wilayah": r["nama_wilayah"], "harga": r["harga_rata2"]}
            for r in chart_rows
        ],
        "chart_cv": [
            {"komoditas": r["komoditas"], "cv": r["cv_persen"]} for r in cv_ranking
        ],
    })
    return render(request, "regional_comparison/index.html", context)
```

**`templatetags/regional_filters.py`** (format angka ala Indonesia, mis. `Rp 15.259` dan `+93,33%`):

```python
"""Filter template kecil untuk format angka gaya Indonesia (titik ribuan, koma desimal)."""
from django import template

register = template.Library()


def _id_number(value, decimals=0):
    """15258.79 -> '15.259' (decimals=0) atau '15.258,79' (decimals=2)."""
    text = f"{abs(float(value)):,.{decimals}f}"
    return text.replace(",", "_").replace(".", ",").replace("_", ".")


@register.filter
def rupiah(value):
    """15000 -> 'Rp 15.000'. Nilai kosong -> '-'."""
    if value is None or value == "":
        return "-"
    return f"Rp {_id_number(value)}"


@register.filter
def selisih_rp(value):
    """Selisih dengan tanda: +2000 -> '+Rp 2.000', -2000 -> '-Rp 2.000'."""
    if value is None or value == "":
        return "-"
    sign = "+" if float(value) > 0 else "-" if float(value) < 0 else ""
    return f"{sign}Rp {_id_number(value)}"


@register.filter
def selisih_persen(value):
    """16.67 -> '+16,67%'."""
    if value is None or value == "":
        return "-"
    sign = "+" if float(value) > 0 else "-" if float(value) < 0 else ""
    return f"{sign}{_id_number(value, 2)}%"


@register.filter
def persen(value):
    """16.67 -> '16,67%'."""
    if value is None or value == "":
        return "-"
    return f"{_id_number(value, 2)}%"


@register.filter
def warna_selisih(value):
    """Kelas warna Tailwind: lebih mahal = merah, lebih murah = hijau."""
    if value is None or value == "" or float(value) == 0:
        return "text-slate-600"
    return "text-red-600" if float(value) > 0 else "text-emerald-600"
```

**`tests.py`** (ganti seluruh isi):

```python
from unittest.mock import patch

import mongomock
from django.test import TestCase
from django.urls import reverse

from .templatetags import regional_filters as f


def seeded_db():
    """MongoDB palsu berisi data kecil, meniru koleksi hasil pipeline."""
    db = mongomock.MongoClient().pangan_pulse
    db.regional_comparison_prices.insert_many([
        {"level": "provinsi", "periode": "2026-10", "komoditas": "BERAS MEDIUM",
         "kode_wilayah": "11", "nama_wilayah": "Aceh", "provinsi": "Aceh",
         "harga_rata2": 14000.0, "rata2_antarwilayah": 13000.0, "selisih_rp": 1000.0,
         "selisih_persen": 7.69, "selisih_vs_termurah_rp": 2000.0, "peringkat": 1,
         "total_wilayah": 2},
        {"level": "provinsi", "periode": "2026-10", "komoditas": "BERAS MEDIUM",
         "kode_wilayah": "12", "nama_wilayah": "Sumatera Utara", "provinsi": "Sumatera Utara",
         "harga_rata2": 12000.0, "rata2_antarwilayah": 13000.0, "selisih_rp": -1000.0,
         "selisih_persen": -7.69, "selisih_vs_termurah_rp": 0.0, "peringkat": 2,
         "total_wilayah": 2},
    ])
    db.regional_comparison_summary.insert_many([
        {"level": "provinsi", "periode": "2026-10", "komoditas": "BERAS MEDIUM",
         "n_wilayah": 2, "harga_rata2": 13000.0, "harga_min": 12000.0, "harga_max": 14000.0,
         "wilayah_termurah": "Sumatera Utara", "wilayah_termahal": "Aceh",
         "selisih_max_min_rp": 2000.0, "disparitas_persen": 16.67,
         "cv_persen": 10.88, "kategori_disparitas": "Rendah"},
    ])
    return db


class RegionalComparisonViewTest(TestCase):
    url = reverse("regional_comparison:index")

    def test_halaman_menampilkan_ringkasan_dan_peringkat(self):
        with patch("apps.regional_comparison.services.get_db", return_value=seeded_db()):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Sumatera Utara")
        self.assertContains(resp, "Rp 14.000")
        self.assertContains(resp, "10,88%")  # CV dalam format Indonesia

    def test_parameter_salah_memakai_default(self):
        with patch("apps.regional_comparison.services.get_db", return_value=seeded_db()):
            resp = self.client.get(self.url, {"level": "ngawur", "periode": "1999-01"})
        self.assertEqual(resp.status_code, 200)
        self.assertEqual(resp.context["level"], "provinsi")
        self.assertEqual(resp.context["periode"], "2026-10")

    def test_data_kosong_menampilkan_pesan(self):
        empty = mongomock.MongoClient().pangan_pulse
        with patch("apps.regional_comparison.services.get_db", return_value=empty):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Data belum tersedia")


class FilterTest(TestCase):
    def test_format_angka_indonesia(self):
        self.assertEqual(f.rupiah(15258.79), "Rp 15.259")
        self.assertEqual(f.selisih_rp(-2000), "-Rp 2.000")
        self.assertEqual(f.selisih_persen(16.667), "+16,67%")
        self.assertEqual(f.rupiah(None), "-")
```

### 6.3 Template halaman: `backend/templates/regional_comparison/index.html`
Buat folder `regional_comparison` di dalam `backend/templates/`, lalu file ini. Halaman memakai Tailwind CSS dan Plotly lewat CDN, jadi **butuh internet** saat dibuka.

```html
{% extends "base.html" %}
{% load regional_filters %}

{% block title %}Perbandingan Harga Antarwilayah | PanganPulse{% endblock %}

{% block content %}
<script src="https://cdn.tailwindcss.com"></script>
<script src="https://cdn.plot.ly/plotly-2.35.2.min.js"></script>

<div class="min-h-screen bg-slate-50 text-slate-800">
  <div class="mx-auto max-w-6xl px-4 py-8">

    <h1 class="text-2xl font-bold">Perbandingan Harga Antarwilayah</h1>
    <p class="mt-1 text-slate-600">
      Bandingkan harga rata-rata bulanan satu komoditas di seluruh wilayah:
      selisih harga, peringkat, dan tingkat disparitas (Coefficient of Variation).
    </p>

    {% if error %}
      <div class="mt-6 rounded-lg border border-amber-300 bg-amber-50 p-4 text-amber-900">{{ error }}</div>
    {% else %}

    <!-- FILTER -->
    <form method="get" class="mt-6 grid gap-4 rounded-xl bg-white p-4 shadow-sm sm:grid-cols-4">
      <label class="block text-sm font-medium">Komoditas
        <select name="komoditas" class="mt-1 w-full rounded-md border border-slate-300 p-2">
          {% for c in commodities %}
            <option value="{{ c }}" {% if c == komoditas %}selected{% endif %}>{{ c }}</option>
          {% endfor %}
        </select>
      </label>
      <label class="block text-sm font-medium">Periode
        <select name="periode" class="mt-1 w-full rounded-md border border-slate-300 p-2">
          {% for p in periods %}
            <option value="{{ p }}" {% if p == periode %}selected{% endif %}>{{ p }}</option>
          {% endfor %}
        </select>
      </label>
      <label class="block text-sm font-medium">Level wilayah
        <select name="level" class="mt-1 w-full rounded-md border border-slate-300 p-2">
          {% for key, label in levels.items %}
            <option value="{{ key }}" {% if key == level %}selected{% endif %}>{{ label }}</option>
          {% endfor %}
        </select>
      </label>
      <div class="flex items-end">
        <button type="submit" class="w-full rounded-md bg-emerald-600 px-4 py-2 font-semibold text-white hover:bg-emerald-700">Tampilkan</button>
      </div>
    </form>

    {% if summary %}
    <!-- KARTU RINGKASAN -->
    <div class="mt-6 grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <div class="rounded-xl bg-white p-4 shadow-sm">
        <div class="text-sm text-slate-500">Termurah</div>
        <div class="text-lg font-bold text-emerald-600">{{ summary.harga_min|rupiah }}</div>
        <div class="text-sm">{{ summary.wilayah_termurah }}</div>
      </div>
      <div class="rounded-xl bg-white p-4 shadow-sm">
        <div class="text-sm text-slate-500">Termahal</div>
        <div class="text-lg font-bold text-red-600">{{ summary.harga_max|rupiah }}</div>
        <div class="text-sm">{{ summary.wilayah_termahal }}</div>
      </div>
      <div class="rounded-xl bg-white p-4 shadow-sm">
        <div class="text-sm text-slate-500">Selisih termahal - termurah</div>
        <div class="text-lg font-bold">{{ summary.selisih_max_min_rp|rupiah }}</div>
        <div class="text-sm">{{ summary.disparitas_persen|persen }} di atas harga termurah</div>
      </div>
      <div class="rounded-xl bg-white p-4 shadow-sm">
        <div class="text-sm text-slate-500">Coefficient of Variation (CV)</div>
        <div class="text-lg font-bold">{{ summary.cv_persen|persen }}</div>
        <div class="text-sm">Disparitas: <span class="font-semibold">{{ summary.kategori_disparitas|default:"-" }}</span>
          &middot; rata-rata {{ summary.harga_rata2|rupiah }} ({{ summary.n_wilayah }} wilayah)</div>
      </div>
    </div>
    <p class="mt-2 text-xs text-slate-500">
      CV = simpangan baku harga antarwilayah &divide; rata-rata &times; 100%. Makin besar CV, makin timpang harga antarwilayah.
      Kategori: Rendah &lt; 15%, Sedang 15&ndash;30%, Tinggi &ge; 30%.
    </p>

    <!-- GRAFIK PERINGKAT -->
    <div class="mt-6 rounded-xl bg-white p-4 shadow-sm">
      <h2 class="font-semibold">Harga {{ komoditas }} per {{ level_label }} &mdash; {{ periode }}</h2>
      {% if chart_note %}<p class="text-xs text-slate-500">{{ chart_note }}</p>{% endif %}
      <div id="chart-ranking" class="mt-2 h-96"></div>
    </div>

    <!-- TABEL PERINGKAT -->
    <div class="mt-6 rounded-xl bg-white p-4 shadow-sm">
      <h2 class="font-semibold">Peringkat wilayah (1 = paling mahal)</h2>
      <div class="mt-2 max-h-[32rem] overflow-auto">
        <table class="w-full text-sm">
          <thead class="sticky top-0 bg-slate-100 text-left">
            <tr>
              <th class="p-2">#</th>
              <th class="p-2">Wilayah</th>
              {% if level == "kabupaten_kota" %}<th class="p-2">Provinsi</th>{% endif %}
              <th class="p-2 text-right">Harga rata-rata</th>
              <th class="p-2 text-right">Selisih vs rata-rata</th>
              <th class="p-2 text-right">Selisih (%)</th>
              <th class="p-2 text-right">Selisih vs termurah</th>
            </tr>
          </thead>
          <tbody>
          {% for r in ranking %}
            <tr class="border-t border-slate-100">
              <td class="p-2">{{ r.peringkat }}</td>
              <td class="p-2">{{ r.nama_wilayah }}</td>
              {% if level == "kabupaten_kota" %}<td class="p-2">{{ r.provinsi }}</td>{% endif %}
              <td class="p-2 text-right">{{ r.harga_rata2|rupiah }}</td>
              <td class="p-2 text-right {{ r.selisih_rp|warna_selisih }}">{{ r.selisih_rp|selisih_rp }}</td>
              <td class="p-2 text-right {{ r.selisih_persen|warna_selisih }}">{{ r.selisih_persen|selisih_persen }}</td>
              <td class="p-2 text-right">{{ r.selisih_vs_termurah_rp|rupiah }}</td>
            </tr>
          {% endfor %}
          </tbody>
        </table>
      </div>
    </div>
    {% else %}
      <div class="mt-6 rounded-lg border border-slate-200 bg-white p-4">
        Tidak ada data untuk kombinasi ini (komoditas mungkin belum tercatat pada periode tersebut).
      </div>
    {% endif %}

    <!-- DISPARITAS ANTAR KOMODITAS -->
    <div class="mt-6 rounded-xl bg-white p-4 shadow-sm">
      <h2 class="font-semibold">Komoditas dengan harga paling timpang antar {{ level_label|lower }} ({{ periode }})</h2>
      <div id="chart-cv" class="mt-2 h-[28rem]"></div>
    </div>

    {% endif %}
  </div>
</div>

{% if not error %}
{{ chart_ranking|json_script:"data-ranking" }}
{{ chart_cv|json_script:"data-cv" }}
<script>
  const ranking = JSON.parse(document.getElementById("data-ranking").textContent);
  const cv = JSON.parse(document.getElementById("data-cv").textContent);
  const cfg = { responsive: true, displayModeBar: false };

  if (ranking.length) {
    Plotly.newPlot("chart-ranking", [{
      type: "bar",
      x: ranking.map(r => r.wilayah),
      y: ranking.map(r => r.harga),
      marker: { color: "#059669" },
      hovertemplate: "%{x}<br>Rp %{y:,.0f}<extra></extra>",
    }], {
      margin: { t: 10, b: 120, l: 70, r: 10 },
      xaxis: { tickangle: -45, automargin: true },
      yaxis: { title: "Harga rata-rata (Rp)" },
    }, cfg);
  }

  if (cv.length) {
    const rows = cv.slice().reverse();   // CV tertinggi tampil di atas
    Plotly.newPlot("chart-cv", [{
      type: "bar", orientation: "h",
      x: rows.map(r => r.cv),
      y: rows.map(r => r.komoditas),
      marker: { color: "#0ea5e9" },
      hovertemplate: "%{y}<br>CV %{x:.2f}%<extra></extra>",
    }], {
      margin: { t: 10, b: 40, l: 260, r: 10 },
      xaxis: { title: "Coefficient of Variation (%)" },
    }, cfg);
  }
</script>
{% endif %}
{% endblock %}
```

### Jalankan

Pastikan Airflow sudah mengisi MongoDB (Bagian 5) dan kontainer `mongo` menyala. Di terminal VS Code dengan `(.venv)` aktif:

```powershell
cd backend
python manage.py test apps.regional_comparison
python manage.py runserver
```

Buka http://127.0.0.1:8000/perbandingan-wilayah/

**Kamu berhasil kalau:**
- Tes: `Ran 4 tests ... OK`.
- Halaman menampilkan filter, 4 kartu ringkasan (termurah, termahal, selisih, CV), grafik batang, tabel peringkat, dan grafik "komoditas paling timpang".
- Contoh pada data saat ini: pilih **BERAS MEDIUM**, periode **2026-10**, level **Provinsi** → termurah **Jawa Timur Rp 13.178**, termahal **Papua Pegunungan Rp 29.500**, rata-rata **Rp 15.259**, CV **21,22%** (Sedang).
- Kalau muncul kotak kuning "Tidak dapat terhubung ke MongoDB" atau "Data belum tersedia", lihat Bagian 10.

Hentikan server dengan `Ctrl+C`.

---

## Bagian 7 — Semua tes sekaligus

```powershell
# dari folder etl (venv aktif)
python -m unittest discover -s tests

# dari folder backend
python manage.py test apps.regional_comparison
```
Hasil yang benar: 9 tes ETL lolos dan 4 tes Django lolos.

---

## Bagian 8 — Commit dan Pull Request

1. Klik ikon **Source Control** di kiri (cabang bercabang, atau `Ctrl+Shift+G`).
2. Periksa daftar file berubah. Yang seharusnya ada: file baru di `etl/pangan_etl`, `etl/tests`, `airflow/dags`, `docker`, `backend/apps/regional_comparison`, `backend/templates/regional_comparison`, serta perubahan di `settings.py`, `urls.py`, `.gitignore`, `etl/requirements.txt`. **File `.csv` di `processed/` tidak boleh ikut** (sudah di-ignore).
3. Arahkan kursor ke tulisan **Changes** lalu klik **+** (stage semua).
4. Isi kotak pesan, misalnya: `Tambah fitur Regional Comparison (metrik, DAG Airflow, halaman Django)`, klik **Commit**.
5. Klik **Publish Branch**.
6. Buka halaman repo di GitHub, klik tombol hijau **Compare & pull request** → **Create pull request**. Minta teman me-review lalu merge.

Sebelum merge, beri tahu timmu (Bagian 11).

---

## Bagian 9 — Cara menjelaskan fitur ini (untuk laporan dan presentasi)

**Selisih harga.** Seperti membandingkan harga bakso di tiap kantin dengan rata-rata semua kantin. Rata-rata beras medium antarprovinsi (Okt 2026) Rp 15.259. Papua Pegunungan Rp 29.500, artinya **+Rp 14.241 atau +93,33%** di atas rata-rata. Jawa Timur Rp 13.178, artinya **-Rp 2.081 atau -13,64%**.

**Peringkat.** Seperti klasemen: peringkat 1 = paling mahal. Pada contoh di atas, Papua Pegunungan peringkat 1 dan Jawa Timur peringkat 38 dari 38 provinsi.

**CV (Coefficient of Variation).** Mengukur *seberapa timpang* harga antarwilayah **dalam persen**. Rumus: simpangan baku ÷ rata-rata × 100%. Mengapa tidak cukup memakai selisih Rp? Karena selisih Rp 5.000 pada beras (Rp 15 ribu) sangat besar, tetapi pada daging sapi (Rp 140 ribu) kecil. Karena CV berupa persen, beras dan daging sapi bisa dibandingkan secara adil. Contoh: beras medium Okt 2026 punya CV 21,22%. Komoditas paling timpang di bulan itu: bawang merah (CV 39,01%), cabai merah (31,40%), cabai rawit (30,75%); paling merata: daging sapi (10,24%).

**Airflow.** Manajer yang menjalankan lima langkah ETL berurutan (cek file → bersihkan → hitung metrik → muat ke MongoDB → validasi). Kalau satu langkah gagal, langkah berikutnya tidak jalan dan Airflow mencoba ulang sekali. Seluruh riwayat dan log bisa dilihat di web Airflow. Satu rangkaian ini disebut **DAG** (urutan langkah satu arah, tanpa putaran).

**Keputusan desain yang bisa kamu bela kalau ditanya dosen:**

| Pertanyaan | Jawaban |
|---|---|
| Kenapa metrik dihitung di ETL, bukan saat halaman dibuka? | Halaman jadi cepat (hanya membaca hasil), dan perhitungannya terdokumentasi sebagai bagian pipeline. |
| Kenapa harga provinsi = rata-rata harga kab/kota? | Agar tiap kab/kota berbobot sama, dan wilayah yang datanya lebih banyak tidak mendominasi. |
| Kenapa kunci wilayah bukan kode daerah? | Kode 2025 dan 2026 berbeda untuk wilayah yang sama (contoh Kota Dumai), sehingga 514 wilayah terhitung 544. Nama provinsi + kab/kota stabil. |
| Kenapa simpangan baku sampel (n−1)? | Wilayah yang ada dianggap sampel dari kondisi harga yang lebih luas, dan ini bawaan pandas. Untuk 38 provinsi bedanya dengan simpangan baku populasi hanya sekitar 1,3%. |
| Kenapa MongoDB? | Sesuai arsitektur proyek (NoSQL), dan satu dokumen sudah memuat semua metrik satu wilayah sehingga query halaman sederhana. |
| Kenapa DAG dijadwalkan mingguan? | Data sumber diperbarui berkala, jadi pipeline diulang otomatis; saat demo cukup dipicu manual. |

---

## Bagian 10 — Masalah umum

| Gejala | Penyebab dan solusi |
|---|---|
| `ModuleNotFoundError: No module named 'pangan_etl'` | Perintahnya harus dijalankan dari **folder `etl`** (`cd etl`), bukan dari folder utama. |
| `.venv\Scripts\Activate.ps1` ditolak | Jalankan `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned` lalu ulangi. |
| `docker: command not found` / "cannot connect to the Docker daemon" | Docker Desktop belum terbuka atau belum *Engine running*. Buka, tunggu hijau. |
| `port is already allocated` untuk 8080 atau 27018 | Ada program lain memakai port itu. Tutup, atau ubah angka kiri pada `ports:` di compose (mis. `"8081:8080"`) lalu buka http://localhost:8081. |
| DAG tidak muncul di Airflow | Tunggu 30–60 detik, refresh. Cek `docker compose -f docker-compose.airflow.yml logs airflow` untuk pesan error. Bagian atas halaman DAG juga menampilkan *DAG Import Errors* kalau ada salah ketik. |
| Task `bersihkan_ringkas_bulanan` gagal dengan `-9` / dibunuh | Memori Docker kurang. Buat file `C:\Users\<namamu>\.wslconfig` berisi `[wsl2]` dan `memory=6GB`, jalankan `wsl --shutdown`, buka ulang Docker Desktop. |
| Task `muat_ke_mongodb` gagal `ServerSelectionTimeoutError` | Kontainer `mongo` tidak menyala. Cek `docker ps`; nyalakan dengan `docker compose -f docker-compose.airflow.yml up -d`. |
| Halaman Django: "Tidak dapat terhubung ke MongoDB" | Kontainer `mongo` mati, atau `MONGO_URI` tidak sama dengan port compose (27018). |
| Halaman Django: "Data belum tersedia" | DAG belum pernah sukses. Jalankan DAG dan tunggu 5 kotak hijau. |
| Halaman tampil tanpa gaya/grafik | Laptop tidak terhubung internet (Tailwind dan Plotly dimuat dari CDN). |
| Port 27017 sudah dipakai MongoDB lokal | Tidak masalah: proyek ini sengaja memakai 27018 agar tidak bentrok. |
| Git: file `.csv` besar ikut ter-stage | Pastikan tiga baris `regional_*.csv` sudah ada di `.gitignore`, lalu `git rm --cached <file>`. |

---

## Bagian 11 — Yang perlu kamu sampaikan ke tim

1. **Dua file bersama kuubah sedikit:** `backend/config/settings.py` (blok MongoDB di bawah) dan `backend/config/urls.py` (satu baris `path`). Kalau teman mengedit file yang sama, mungkin muncul *merge conflict*: simpan kedua perubahan.
2. **Port MongoDB 27018 dan nama database `pangan_pulse`** dipakai fitur ini. Kalau tim sepakat memakai MongoDB lain, cukup ubah variabel `MONGO_URI` / `MONGO_DB_NAME` (di `config.py` dan `settings.py`), tidak perlu mengubah kode lain.
3. **`COMMODITY_MAPPING` disalin dari `ETL.ipynb`** ke `etl/pangan_etl/config.py`. Kalau mapping di notebook berubah, ubah juga di sini. (Usul: nanti notebook cukup `from pangan_etl.config import COMMODITY_MAPPING` agar tidak ada dua salinan.)
4. **Dua catatan data untuk tim ETL:** (a) `IKAN KEMBUNG` (2026) dan `IKAN KEMBUNG/IKAN GEMBUNG/ IKAN BANYAR/...` (2025) masih terhitung dua komoditas berbeda, sehingga masing-masing hanya punya data setahun; kalau tim memutuskan keduanya sama, tambahkan ke mapping. (b) Kode daerah 2025 vs 2026 tidak konsisten (lihat Bagian 0), sebaiknya diketahui juga oleh yang mengerjakan clustering.
5. Fitur ini **tidak mengubah** `ETL.ipynb`, app `dashboard`, `price_analysis`, maupun `regional_clustering`.
