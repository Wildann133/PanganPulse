from django.http import JsonResponse
from django.shortcuts import render
from django.views.decorators.http import require_GET
from pymongo.errors import PyMongoError

from utils.mongo import get_db

from . import services


@require_GET
def home(request):
    """Beranda: Dashboard Overview. Datanya diambil browser dari /api/ringkasan."""
    return render(request, "dashboard/home.html")


@require_GET
def api_ringkasan(request):
    """JSON untuk Dashboard Overview. Parameter (daftar putih): `periode` (YYYY-MM), `ukuran` (median | rata_rata)."""
    try:
        data = services.bangun_ringkasan(
            get_db(),
            periode=request.GET.get("periode") or None,
            ukuran=request.GET.get("ukuran", "median"),
        )
    except services.ParameterTidakValid as exc:
        return JsonResponse({"error": str(exc)}, status=400)
    except services.DataBelumSiap as exc:
        return JsonResponse({"error": str(exc)}, status=503)
    except PyMongoError:
        return JsonResponse({"error": "MongoDB tidak dapat dijangkau"}, status=503)
    return JsonResponse(data, json_dumps_params={"ensure_ascii": False})
