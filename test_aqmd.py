import datetime
import time
from unittest import TestCase

import aqmd

class TestAQMDSensor(TestCase):
    def test_parse_aqi_csv_current(self):
        with open('Current_Air_Quality_Feature.csv', 'rt') as stream:
            data = stream.read()
            table = aqmd.parse_aqi_csv(data, aqmd.CURRENT_LABELS)
            self.assertIn(3, table)
            current = table[3]
            for label in aqmd.CURRENT_LABELS:
                self.assertIn(label, current)

            self.assertIsInstance(current['current_datetime'],
                                  datetime.datetime)
                

    def test_parse_aqi_csv_forecast(self):
        with open('Tomorrows_Forecast_Feature.csv', 'rt') as stream:
            data = stream.read()
            table = aqmd.parse_aqi_csv(data, aqmd.FORECAST_LABELS)
            self.assertIn(3, table)
            current = table[3]
            for label in aqmd.FORECAST_LABELS:
                self.assertIn(label, current)

            self.assertIsInstance(current['date'],
                                  datetime.date)

    def test_aqmd_cache(self):
        with open('Current_Air_Quality_Feature.csv', 'rt') as stream:
            data = stream.read()
        aqmd_cache = aqmd.AQMDCache(aqmd.SCAQMD_CURRENT_CSV, True)
        self.assertEqual(aqmd_cache.last_update, 0)
        timestamp = time.time()
        aqmd_cache.current = aqmd.parse_aqi_csv(data, aqmd_cache.labels)
        self.assertGreaterEqual(aqmd_cache.last_update, timestamp)

    def test_aqmd_sensor(self):
        with open('Current_Air_Quality_Feature.csv', 'rt') as stream:
            data = stream.read()
        aqmd_cache = aqmd.AQMDCache(aqmd.SCAQMD_CURRENT_CSV, True)
        aqmd_cache.current = aqmd.parse_aqi_csv(data, aqmd_cache.labels)
        sensor = aqmd.AQMDSensor(aqmd_cache, 3)

        self.assertEqual(sensor.name, "Southwest Coastal LA County Current Air Quality")
        self.assertEqual(sensor.state, 33)
