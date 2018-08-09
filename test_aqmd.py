import datetime
import time
from unittest import TestCase

import aqmd

EXPECTED_CURRENT_LABELS = [
    'sra', 'name', 'aqi', 'current_datetime',
    'category_desc', 'pollutant_desc', 'link']
EXPECTED_FORECAST_LABELS = [
    'sra', 'name', 'aqi', 'date', 'category_desc', 'pollutant_desc']

class TestAQMDSensor(TestCase):
    def test_parse_aqi_csv_current(self):
        with open('Current_Air_Quality_Feature.csv', 'rb') as stream:
            data = stream.read()
            table = aqmd.parse_aqi_csv(data)
            self.assertIn(3, table)
            current = table[3]
            for label in EXPECTED_CURRENT_LABELS:
                self.assertIn(label, current)

            self.assertIsInstance(current['current_datetime'],
                                  datetime.datetime)

    def test_parse_aqi_csv_forecast(self):
        with open('Tomorrows_Forecast_Feature.csv', 'rb') as stream:
            data = stream.read()
            table = aqmd.parse_aqi_csv(data)
            self.assertIn(3, table)
            current = table[3]
            for label in EXPECTED_FORECAST_LABELS:
                self.assertIn(label, current)

            self.assertIsInstance(current['date'],
                                  datetime.date)

    def test_aqmd_cache_current(self):
        with open('Current_Air_Quality_Feature.csv', 'rb') as stream:
            data = stream.read()
        aqmd_cache = aqmd.AQMDCache()
        timestamp = time.time()
        aqmd_cache[aqmd.DEFAULT_CURRENT_URL] = data
        record = aqmd_cache[aqmd.DEFAULT_CURRENT_URL]
        print(record.table.keys())
        self.assertIn(3, record.table)
        self.assertEquals(record.is_current, True)
        self.assertGreaterEqual(record.last_updated, timestamp)

    def test_aqmd_cache_forecast(self):
        with open('Tomorrows_Forecast_Feature.csv', 'rb') as stream:
            data = stream.read()
        aqmd_cache = aqmd.AQMDCache()
        timestamp = time.time()
        aqmd_cache[aqmd.DEFAULT_FORECAST_URL] = data
        record = aqmd_cache[aqmd.DEFAULT_FORECAST_URL]
        self.assertIn(3, record.table)
        self.assertEquals(record.is_current, False)
        self.assertGreaterEqual(record.last_updated, timestamp)

    def test_aqmd_sensor_current(self):
        with open('Current_Air_Quality_Feature.csv', 'rb') as stream:
            data = stream.read()
        aqmd_cache = aqmd.AQMDCache()
        aqmd_cache[aqmd.DEFAULT_CURRENT_URL] = data
        sensor = aqmd.AQMDSensor(aqmd.DEFAULT_CURRENT_URL, 3, aqmd_cache=aqmd_cache)

        self.assertEqual(sensor.name, "Southwest Coastal LA County Current Air Quality")
        self.assertEqual(sensor.state, 33)
