"""
Test tahap LOAD memakai MongoDB palsu (mongomock) - tidak perlu server Mongo.
Instal dulu:  pip install mongomock
"""
import unittest

import bson
import mongomock

from pangan_etl import load_mongo
from pangan_etl.regional_metrics import compute_regional_comparison
from tests.test_regional_metrics import sample_monthly


class LoadMongoTest(unittest.TestCase):
    def test_records_valid_untuk_bson_dan_nan_jadi_none(self):
        prices, summary = compute_regional_comparison(sample_monthly().iloc[:1])
        for df in (prices, summary):
            for rec in load_mongo._to_records(df):
                bson.encode(rec)  # error jika ada tipe numpy / NaN yang tidak valid
        rec = load_mongo._to_records(summary)[0]
        self.assertIsNone(rec["cv_persen"])

    def test_replace_collection_tidak_menggandakan_data(self):
        prices, _ = compute_regional_comparison(sample_monthly())
        col = mongomock.MongoClient().db.coll
        load_mongo._replace_collection(col, prices)
        load_mongo._replace_collection(col, prices)  # dijalankan dua kali
        self.assertEqual(col.count_documents({}), len(prices))


if __name__ == "__main__":
    unittest.main()
