from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET

from .services import get_filter_options, get_price_detail, get_price_trend


@require_GET
def index(request):
    """Halaman utama fitur Price Trend Analysis."""
    try:
        options = get_filter_options()
    except Exception:
        options = {
            "komoditas": [],
            "kabupaten_kota": [],
            "provinsi": [],
            "wilayah_detail": [],
            "periode": [],
            "min_date": "2025-01-01",
            "max_date": "2026-12-31",
        }

    context = {
        "page_title": "Price Trend Analysis",
        "filter_options": options,
    }
    return render(request, "price_analysis/index.html", context)


@require_GET
def api_filter_options(request):
    """Endpoint JSON untuk mengambil opsi filter komoditas, wilayah, dan periode."""
    try:
        data = get_filter_options()
        return JsonResponse({"status": "ok", "data": data}, status=200)
    except Exception as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=500)


@require_GET
def api_price_trend(request):
    """
    Endpoint JSON /api/tren/
    Query params: komoditas, kabupaten_kota (atau wilayah), periode (YYYY-MM), start_date, end_date.
    """
    komoditas = request.GET.get("komoditas", "").strip()
    kabupaten_kota = (
        request.GET.get("kabupaten_kota", "").strip()
        or request.GET.get("wilayah", "").strip()
    )
    periode = request.GET.get("periode", "").strip() or None
    start_date = request.GET.get("start_date", "").strip() or None
    end_date = request.GET.get("end_date", "").strip() or None

    try:
        result = get_price_trend(
            komoditas=komoditas,
            kabupaten_kota=kabupaten_kota,
            periode=periode,
            start_date=start_date,
            end_date=end_date,
        )
        return JsonResponse({"status": "ok", "data": result}, status=200)
    except ValueError as val_err:
        return JsonResponse({"status": "error", "message": str(val_err)}, status=400)
    except Exception as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=500)


@require_GET
def api_price_detail(request):
    """
    Endpoint JSON /api/detail/ saat pengguna mengklik titik pada grafik tren Plotly.
    """
    komoditas = request.GET.get("komoditas", "").strip()
    kabupaten_kota = (
        request.GET.get("kabupaten_kota", "").strip()
        or request.GET.get("wilayah", "").strip()
    )
    tanggal = request.GET.get("tanggal", "").strip()

    try:
        detail = get_price_detail(
            komoditas=komoditas,
            kabupaten_kota=kabupaten_kota,
            tanggal=tanggal,
        )
        return JsonResponse({"status": "ok", "data": detail}, status=200)
    except ValueError as val_err:
        return JsonResponse({"status": "error", "message": str(val_err)}, status=400)
    except Exception as exc:
        return JsonResponse({"status": "error", "message": str(exc)}, status=500)