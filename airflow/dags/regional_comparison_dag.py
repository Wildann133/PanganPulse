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
