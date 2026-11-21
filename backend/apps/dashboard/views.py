from django.shortcuts import render

from utils.mongo import MONGO_DB_NAME, get_db, ping


def home(request):
    """Beranda sementara: memastikan Django dan MongoDB tersambung.

    Akan diganti dengan Dashboard Overview (endpoint /api/ringkasan + grafik).
    """
    terhubung, detail = ping()
    koleksi = []
    if terhubung:
        db = get_db()
        for nama in sorted(db.list_collection_names()):
            koleksi.append({"nama": nama, "jumlah": db[nama].estimated_document_count()})
    return render(request, "dashboard/home.html", {
        "mongo_terhubung": terhubung,
        "mongo_detail": detail,
        "mongo_db": MONGO_DB_NAME,
        "koleksi": koleksi,
    })
