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
    