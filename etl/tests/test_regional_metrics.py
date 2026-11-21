"""
Unit test untuk perhitungan Regional Comparison.

Jalankan dari folder etl/:
    python -m unittest discover -s tests -v
"""
import unittest

import pandas as pd

from pangan_etl.regional_metrics import (
    classify_cv,
    compute_regional_comparison,
)


def sample_monthly():
    """Data kecil: 1 komoditas, 1 periode, 3 kab/kota di 2 provinsi."""
    return pd.DataFrame({
        "kode_provinsi": ["11", "11", "12"],
        "provinsi": ["Aceh", "Aceh", "Sumut"],
        "kode_daerah": ["1101", "1102", "1201"],
        "kabupaten_kota": ["Kab. A", "Kab. B", "Kab. C"],
        "komoditas": ["BERAS MEDIUM"] * 3,
        "periode": ["2026-01"] * 3,
        "harga_rata2": [10000.0, 12000.0, 14000.0],
        "n_obs": [10, 10, 10],
    })


class RegionalMetricsTest(unittest.TestCase):
    def setUp(self):
        self.prices, self.summary = compute_regional_comparison(sample_monthly())

    def kab(self, nama):
        df = self.prices
        return df[(df.level == "kabupaten_kota") & (df.nama_wilayah == nama)].iloc[0]

    def test_selisih_terhadap_rata_rata(self):
        # rata-rata = 12000
        self.assertEqual(self.kab("Kab. A").selisih_rp, -2000)
        self.assertEqual(self.kab("Kab. C").selisih_rp, 2000)
        self.assertAlmostEqual(self.kab("Kab. C").selisih_persen, 16.67, places=2)

    def test_selisih_terhadap_termurah(self):
        self.assertEqual(self.kab("Kab. A").selisih_vs_termurah_rp, 0)
        self.assertEqual(self.kab("Kab. C").selisih_vs_termurah_rp, 4000)

    def test_peringkat_satu_adalah_termahal(self):
        self.assertEqual(self.kab("Kab. C").peringkat, 1)
        self.assertEqual(self.kab("Kab. B").peringkat, 2)
        self.assertEqual(self.kab("Kab. A").peringkat, 3)

    def test_cv_kabupaten(self):
        # std sampel [10000,12000,14000] = 2000 ; CV = 2000/12000*100
        row = self.summary[self.summary.level == "kabupaten_kota"].iloc[0]
        self.assertAlmostEqual(row.cv_persen, 16.67, places=2)
        self.assertEqual(row.kategori_disparitas, "Sedang")
        self.assertEqual(row.wilayah_termurah, "Kab. A")
        self.assertEqual(row.wilayah_termahal, "Kab. C")
        self.assertEqual(row.selisih_max_min_rp, 4000)

    def test_level_provinsi_memakai_rata_rata_kabkota(self):
        prov = self.prices[self.prices.level == "provinsi"].set_index("nama_wilayah")
        self.assertEqual(prov.loc["Aceh", "harga_rata2"], 11000)  # (10000+12000)/2
        self.assertEqual(prov.loc["Aceh", "jumlah_kabkota"], 2)
        self.assertEqual(prov.loc["Sumut", "peringkat"], 1)

    def test_satu_wilayah_cv_kosong(self):
        one = sample_monthly().iloc[:1]
        _, summary = compute_regional_comparison(one)
        self.assertTrue(summary["cv_persen"].isna().all())

    def test_classify_cv(self):
        self.assertEqual(classify_cv(5), "Rendah")
        self.assertEqual(classify_cv(20), "Sedang")
        self.assertEqual(classify_cv(45), "Tinggi")
        self.assertIsNone(classify_cv(float("nan")))


if __name__ == "__main__":
    unittest.main()
