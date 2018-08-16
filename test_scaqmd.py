#
#    Copyright 2018 Diane Trout
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

from datetime import datetime, date
import time
from unittest import TestCase
from unittest.mock import patch
import pytz

import scaqmd

EXPECTED_CURRENT_LABELS = [
    'sra', 'name', 'aqi', 'current_datetime',
    'category_desc', 'pollutant_desc', 'link']
EXPECTED_FORECAST_LABELS = [
    'sra', 'name', 'aqi', 'date', 'category_desc', 'pollutant_desc']


class TestSCAQMDSensor(TestCase):
    def test_parse_aqi_csv_current(self):
        with open('Current_Air_Quality_Feature.csv', 'rb') as stream:
            data = stream.read()
            table = scaqmd.parse_aqi_csv(data)
            self.assertIn(3, table)
            current = table[3]
            for label in EXPECTED_CURRENT_LABELS:
                self.assertIn(label, current)

            self.assertIsInstance(current['current_datetime'],
                                  datetime)
            self.assertEqual(current['current_datetime'],
                             datetime(2018, 6, 24, 21, 0, 0, tzinfo=pytz.utc))

    def test_parse_aqi_csv_forecast(self):
        with open('Tomorrows_Forecast_Feature.csv', 'rb') as stream:
            data = stream.read()
            table = scaqmd.parse_aqi_csv(data)
            self.assertIn(3, table)
            current = table[3]
            for label in EXPECTED_FORECAST_LABELS:
                self.assertIn(label, current)

            self.assertIsInstance(current['date'],
                                  date)
            # date in the file is in America/Los_Angeles
            expected_date = datetime(2018, 6, 25, 0, 0, 0)
            expected_date = scaqmd.DEFAULT_TIMEZONE.localize(expected_date)
            # Now convert that to UTC, so we only store things in one timezone.
            expected_date = expected_date.astimezone(pytz.utc)
            self.assertEqual(current['date'], expected_date)

    def test_scaqmd_cache_current(self):
        with open('Current_Air_Quality_Feature.csv', 'rb') as stream:
            data = stream.read()
        scaqmd_cache = scaqmd.SCAQMDCache()
        timestamp = time.time()
        scaqmd_cache[scaqmd.DEFAULT_CURRENT_URL] = data
        record = scaqmd_cache[scaqmd.DEFAULT_CURRENT_URL]
        self.assertIn(3, record.table)
        self.assertEquals(record.is_current, True)
        self.assertGreaterEqual(record.last_updated, timestamp)

    def test_scaqmd_cache_forecast(self):
        with open('Tomorrows_Forecast_Feature.csv', 'rb') as stream:
            data = stream.read()
        scaqmd_cache = scaqmd.SCAQMDCache()
        timestamp = time.time()
        scaqmd_cache[scaqmd.DEFAULT_FORECAST_URL] = data
        record = scaqmd_cache[scaqmd.DEFAULT_FORECAST_URL]
        self.assertIn(3, record.table)
        self.assertEquals(record.is_current, False)
        self.assertGreaterEqual(record.last_updated, timestamp)

    def test_scaqmd_sensor_current(self):
        with open('Current_Air_Quality_Feature.csv', 'rb') as stream:
            data = stream.read()
        table = scaqmd.parse_aqi_csv(data)
        self.assertEqual(table[1]['current_datetime'],
                         datetime(2018, 6, 24, 22, 0, tzinfo=pytz.utc))
        self.assertEqual(table[2]['current_datetime'],
                         datetime(2018, 6, 24, 21, 0, tzinfo=pytz.utc))
        scaqmd_cache = scaqmd.SCAQMDCache()
        scaqmd_cache[scaqmd.DEFAULT_CURRENT_URL] = data
        sensor = scaqmd.SCAQMDSensor(scaqmd.DEFAULT_CURRENT_URL, 3, scaqmd_cache=scaqmd_cache)
        self.assertEqual(scaqmd_cache[scaqmd.DEFAULT_CURRENT_URL].valid_timestamp,
                         datetime(2018, 6, 24, 21, 0, tzinfo=pytz.utc))

        self.assertEqual(sensor.name, "Southwest Coastal LA County Current Air Quality")
        self.assertEqual(sensor.state, 33)
        self.assertEqual(sensor.next_update, datetime(2018, 6, 24, 22, 0, tzinfo=pytz.utc))

    def test_scaqmd_sensor_forecast(self):
        with open('Tomorrows_Forecast_Feature.csv', 'rb') as stream:
            data = stream.read()
        scaqmd_cache = scaqmd.SCAQMDCache()
        scaqmd_cache[scaqmd.DEFAULT_CURRENT_URL] = data
        sensor = scaqmd.SCAQMDSensor(scaqmd.DEFAULT_CURRENT_URL, 3, scaqmd_cache=scaqmd_cache)

        self.assertEqual(sensor.name, "Southwest Coastal LA County Tomorrows Forecast Air Quality")
        self.assertEqual(sensor.state, 48)
        # date in the file is in America/Los_Angeles
        expected_date = datetime(2018, 6, 25, 12, 0, 0)
        expected_date = scaqmd.DEFAULT_TIMEZONE.localize(expected_date)
        # Now convert that to UTC, so we only store things in one timezone.
        expected_date = expected_date.astimezone(pytz.utc)
        self.assertEqual(sensor.next_update, expected_date)

    def test_update(self):
        with open('Current_Air_Quality_Feature.csv', 'rb') as stream:
            data = stream.read()
            now = datetime.now().strftime('%Y-%m-%dT%H:00:00.000Z').encode('ascii')
            current_data = data.replace(b'2018-06-24T21:00:00.000Z', now)

        with patch.object(scaqmd.SCAQMDCache, '_update_aqi', return_value=None) as _update_aqi:
            scaqmd_cache = scaqmd.SCAQMDCache()
            scaqmd_cache[scaqmd.DEFAULT_CURRENT_URL] = data
            sensor = scaqmd.SCAQMDSensor(scaqmd.DEFAULT_CURRENT_URL, 3, scaqmd_cache=scaqmd_cache)
            sensor.update()
            _update_aqi.assert_called_with(scaqmd.DEFAULT_CURRENT_URL)
            scaqmd_cache[scaqmd.DEFAULT_CURRENT_URL] = current_data
            _update_aqi.reset_mock()
            sensor.update()
            _update_aqi.assert_not_called()

    def test_update_new_day(self):
        with open('Current_Air_Quality_Feature.csv', 'rb') as stream:
            data = stream.read()
            before_tomorrow = b'2018-06-24T23:00:00.000Z'
            tomorrow = b'2018-06-25T00:00:00.000Z'
            current_data = data.replace(b'2018-06-24T21:00:00.000Z', before_tomorrow)
            current_data = current_data.replace(b'2018-06-24T22:00:00.000Z', tomorrow)
            self.assertNotEquals(data, current_data)

        with patch.object(scaqmd.SCAQMDCache, '_update_aqi', return_value=None) as _update_aqi:
            scaqmd_cache = scaqmd.SCAQMDCache()
            scaqmd_cache[scaqmd.DEFAULT_CURRENT_URL] = current_data
            self.assertEquals(scaqmd_cache[scaqmd.DEFAULT_CURRENT_URL].valid_timestamp,
                              datetime(2018, 6, 24, 23, 0, tzinfo=pytz.utc))
            sensor = scaqmd.SCAQMDSensor(scaqmd.DEFAULT_CURRENT_URL, 3, scaqmd_cache=scaqmd_cache)
            self.assertEquals(sensor.valid_timestamp, datetime(2018, 6, 24, 23, tzinfo=pytz.utc))
            self.assertEquals(sensor.next_update,  datetime(2018, 6, 25, 0, tzinfo=pytz.utc))
