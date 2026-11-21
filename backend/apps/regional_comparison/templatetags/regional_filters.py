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
