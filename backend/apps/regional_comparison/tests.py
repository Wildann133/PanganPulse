from unittest.mock import patch

import mongomock
from django.test import TestCase
from django.urls import reverse

from .templatetags import regional_filters as f


def seeded_db(with_partial_month=False):
    """MongoDB palsu berisi data kecil, meniru koleksi hasil pipeline."""
    db = mongomock.MongoClient().panganpulse
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
    if with_partial_month:
        # bulan terbaru belum lengkap menurut koleksi `periode` milik dashboard
        db.regional_comparison_summary.insert_one(
            {"level": "provinsi", "periode": "2026-11", "komoditas": "BERAS MEDIUM",
             "n_wilayah": 2, "harga_rata2": 13500.0, "harga_min": 12500.0, "harga_max": 14500.0,
             "wilayah_termurah": "Sumatera Utara", "wilayah_termahal": "Aceh",
             "selisih_max_min_rp": 2000.0, "disparitas_persen": 16.0,
             "cv_persen": 10.5, "kategori_disparitas": "Rendah"})
        db.periode.insert_many([
            {"periode": "2026-10", "lengkap": True},
            {"periode": "2026-11", "lengkap": False},
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
        empty = mongomock.MongoClient().panganpulse
        with patch("apps.regional_comparison.services.get_db", return_value=empty):
            resp = self.client.get(self.url)
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, "Data belum tersedia")

class IntegrasiDashboardTest(TestCase):
    """Halaman ini harus menyatu dengan dashboard: navigasi, tautan, dan aturan periode yang sama."""
    url = reverse("regional_comparison:index")

    def test_periode_awal_melewati_bulan_belum_lengkap(self):
        with patch("apps.regional_comparison.services.get_db",
                   return_value=seeded_db(with_partial_month=True)):
            resp = self.client.get(self.url)
        self.assertEqual(resp.context["periode"], "2026-10")  # bukan 2026-11 yang belum lengkap
        self.assertContains(resp, "2026-11 (belum lengkap)")

    def test_bulan_belum_lengkap_diberi_catatan_jika_dipilih(self):
        with patch("apps.regional_comparison.services.get_db",
                   return_value=seeded_db(with_partial_month=True)):
            resp = self.client.get(self.url, {"periode": "2026-11"})
        self.assertEqual(resp.context["periode"], "2026-11")
        self.assertContains(resp, "belum lengkap satu bulan penuh")

    def test_tanpa_koleksi_periode_semua_bulan_dianggap_lengkap(self):
        with patch("apps.regional_comparison.services.get_db", return_value=seeded_db()):
            resp = self.client.get(self.url)
        self.assertNotContains(resp, "belum lengkap")

    def test_navigasi_dan_tautan_kembali_ke_dashboard(self):
        with patch("apps.regional_comparison.services.get_db", return_value=seeded_db()):
            resp = self.client.get(self.url)
        self.assertContains(resp, 'class="pp-nav"')
        self.assertContains(resp, 'aria-current="page">Perbandingan Wilayah')
        self.assertContains(resp, reverse("dashboard:home") + "?periode=2026-10")

    def test_dashboard_punya_navigasi_dan_tautan_ke_perbandingan(self):
        resp = self.client.get(reverse("dashboard:home"))
        self.assertEqual(resp.status_code, 200)
        self.assertContains(resp, 'aria-current="page">Ringkasan Harga')
        self.assertContains(resp, f'data-compare="{self.url}"')

class FilterTest(TestCase):
    def test_format_angka_indonesia(self):
        self.assertEqual(f.rupiah(15258.79), "Rp 15.259")
        self.assertEqual(f.selisih_rp(-2000), "-Rp 2.000")
        self.assertEqual(f.selisih_persen(16.667), "+16,67%")
        self.assertEqual(f.rupiah(None), "-")
    def test_warna_selisih_memakai_kelas_tema(self):
        self.assertEqual(f.warna_selisih(100), "up")
        self.assertEqual(f.warna_selisih(-100), "down")
        self.assertEqual(f.warna_selisih(0), "t-ink2")