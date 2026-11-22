from django.test import SimpleTestCase

from . import services


def dok(median, n=100):
    return {"median": median, "rata_rata": median * 1.1, "n_observasi": n, "n_wilayah": 10, "minimum": median / 2, "maksimum": median * 2}


class BandingkanTests(SimpleTestCase):
    def test_persen_perubahan(self):
        hasil = services.bandingkan({"CABAI": dok(120)}, {"CABAI": dok(100)}, "median")
        self.assertEqual(hasil[0]["perubahan_pct"], 20.0)
        self.assertEqual(hasil[0]["nilai_pembanding"], 100)

    def test_komoditas_tanpa_pembanding_tidak_punya_perubahan(self):
        hasil = services.bandingkan({"BARU": dok(50)}, {"LAMA": dok(40)}, "median")
        self.assertIsNone(hasil[0]["perubahan_pct"])

    def test_memakai_ukuran_yang_dipilih(self):
        hasil = services.bandingkan({"X": dok(100)}, {"X": dok(100)}, "rata_rata")
        self.assertEqual(hasil[0]["nilai"], 110.00000000000001)
        self.assertEqual(hasil[0]["perubahan_pct"], 0.0)


class KpiTests(SimpleTestCase):
    def setUp(self):
        sekarang = {"A": dok(130), "B": dok(95), "C": dok(100), "D": dok(60)}
        sebelumnya = {"A": dok(100), "B": dok(100), "C": dok(100)}
        self.kpi = services.susun_kpi(services.bandingkan(sekarang, sebelumnya, "median"))

    def test_naik_dan_turun_terbesar(self):
        self.assertEqual(self.kpi["naik_terbesar"]["nama"], "A")
        self.assertEqual(self.kpi["turun_terbesar"]["nama"], "B")

    def test_lonjakan_memakai_ambang(self):
        self.assertEqual([k["nama"] for k in self.kpi["lonjakan"]], ["A"])

    def test_tertinggi_dan_terendah(self):
        self.assertEqual(self.kpi["tertinggi"][0]["nama"], "A")
        self.assertEqual(self.kpi["terendah"][0]["nama"], "D")

    def test_tanpa_kenaikan_tidak_ada_naik_terbesar(self):
        kpi = services.susun_kpi(services.bandingkan({"A": dok(90)}, {"A": dok(100)}, "median"))
        self.assertIsNone(kpi["naik_terbesar"])


class PeriodeTests(SimpleTestCase):
    daftar = [
        {"periode": "2026-09", "lengkap": True},
        {"periode": "2026-10", "lengkap": True},
        {"periode": "2026-11", "lengkap": False},
    ]

    def test_periode_awal_melewati_bulan_berjalan(self):
        self.assertEqual(services.pilih_periode_awal(self.daftar), "2026-10")

    def test_periode_sebelumnya(self):
        self.assertEqual(services.periode_sebelumnya(self.daftar, "2026-10"), "2026-09")
        self.assertIsNone(services.periode_sebelumnya(self.daftar, "2026-09"))


class AmbangDanRentangTests(SimpleTestCase):
    def test_ambang_bawaan_dan_pilihan(self):
        self.assertEqual(services.baca_ambang(None), services.AMBANG_LONJAKAN)
        self.assertEqual(services.baca_ambang("15"), 15.0)

    def test_ambang_di_luar_daftar_putih_ditolak(self):
        for mentah in ("7", "abc", "1e9", "-5"):
            with self.assertRaises(services.ParameterTidakValid):
                services.baca_ambang(mentah)

    def test_ambang_mengubah_daftar_lonjakan(self):
        data = services.bandingkan({"A": dok(112), "B": dok(103)}, {"A": dok(100), "B": dok(100)}, "median")
        self.assertEqual([k["nama"] for k in services.susun_kpi(data, 10.0)["lonjakan"]], ["A"])
        self.assertEqual([k["nama"] for k in services.susun_kpi(data, 5.0)["lonjakan"]], ["A"])
        self.assertEqual(services.susun_kpi(data, 20.0)["lonjakan"], [])

    def test_bandingkan_membawa_rentang_dan_wilayah(self):
        item = services.bandingkan({"A": dok(100)}, {}, "median")[0]
        self.assertEqual((item["minimum"], item["maksimum"], item["n_wilayah"]), (50, 200, 10))
