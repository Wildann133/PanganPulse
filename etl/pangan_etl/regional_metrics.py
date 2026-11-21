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
