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
