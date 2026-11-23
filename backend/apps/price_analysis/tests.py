from datetime import datetime
from unittest.mock import MagicMock, patch
from django.test import Client, TestCase
from django.urls import reverse

from .services import get_price_trend


class PriceTrendServiceTests(TestCase):
    @patch("apps.price_analysis.services.get_db")
    def test_get_price_trend_calculates_delta_and_summary(self, mock_get_db):
        mock_db = MagicMock()
        mock_db.komoditas.find.return_value.sort.return_value = [{"nama": "Cabai Merah"}]
        mock_db.wilayah.find.return_value.sort.return_value = [
            {"provinsi": "ACEH", "kabupaten_kota": "KAB. SIMEULUE"}
        ]
        mock_db.harga_pangan.distinct.return_value = ["2025-01"]

        mock_db.harga_pangan.aggregate.side_effect = [
            [{"_id": None, "min_date": datetime(2025, 1, 1), "max_date": datetime(2025, 1, 3)}],
            [
                {
                    "_id": datetime(2025, 1, 1),
                    "provinsi": "ACEH",
                    "harga_rata2": 40000.0,
                    "harga_min": 40000.0,
                    "harga_max": 40000.0,
                    "jumlah_observasi": 1,
                },
                {
                    "_id": datetime(2025, 1, 2),
                    "provinsi": "ACEH",
                    "harga_rata2": 42000.0,
                    "harga_min": 42000.0,
                    "harga_max": 42000.0,
                    "jumlah_observasi": 1,
                },
                {
                    "_id": datetime(2025, 1, 3),
                    "provinsi": "ACEH",
                    "harga_rata2": 44000.0,
                    "harga_min": 44000.0,
                    "harga_max": 44000.0,
                    "jumlah_observasi": 1,
                },
            ],
        ]
        mock_get_db.return_value = mock_db

        result = get_price_trend(
            komoditas="Cabai Merah",
            kabupaten_kota="KAB. SIMEULUE",
            periode="2025-01",
        )

        self.assertEqual(result["meta"]["total_points"], 3)
        self.assertEqual(result["meta"]["provinsi"], "ACEH")
        self.assertEqual(result["summary"]["harga_awal"], 40000.0)
        self.assertEqual(result["summary"]["harga_akhir"], 44000.0)
        self.assertEqual(result["summary"]["selisih_rp"], 4000.0)
        self.assertEqual(result["summary"]["selisih_persen"], 10.0)
        self.assertEqual(result["series"][1]["perubahan_rp"], 2000.0)


class PriceTrendApiViewsTests(TestCase):
    def setUp(self):
        self.client = Client()

    def test_api_tren_missing_params_returns_400(self):
        response = self.client.get(reverse("price_analysis:api_tren"))
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.json()["status"], "error")

    @patch("apps.price_analysis.views.get_price_trend")
    def test_api_tren_success_returns_200(self, mock_trend):
        mock_trend.return_value = {
            "meta": {"komoditas": "Cabai Merah", "kabupaten_kota": "KAB. SIMEULUE", "total_points": 1},
            "summary": {"harga_awal": 45000.0, "harga_akhir": 45000.0, "status_tren": "Stabil"},
            "series": [{"tanggal": "2025-01-01", "harga": 45000.0}],
        }

        response = self.client.get(
            reverse("price_analysis:api_tren"),
            {"komoditas": "Cabai Merah", "wilayah": "KAB. SIMEULUE"},
        )
        self.assertEqual(response.status_code, 200)
        payload = response.json()
        self.assertEqual(payload["status"], "ok")
        self.assertEqual(payload["data"]["summary"]["status_tren"], "Stabil")