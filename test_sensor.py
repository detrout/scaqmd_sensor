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
import asyncio
from datetime import datetime
from unittest import TestCase, main
from unittest.mock import patch

from bs4 import BeautifulSoup
from scaqmd import sensor

AQ_DETAILS = 'AQ Details - Current Air Quality.html'


async def fake_fetch_state(*args):
    with open(AQ_DETAILS, 'rt') as instream:
        return instream.read()


class TestCurrentAQI(TestCase):
    def test_parse(self):
        s = sensor.CurrentAQI(4, None)
        with open(AQ_DETAILS, 'rt') as instream:
            self.assertEqual(s.last_update, datetime(1, 1, 1))
            self.assertEqual(s.next_update, datetime(1, 1, 1))
            self.assertEqual(s.name, None)
            self.assertEqual(s.carbon_monoxide, None)
            self.assertEqual(s.nitrogen_dioxide, None)
            self.assertEqual(s.particulate_matter_10, None)

            tree = BeautifulSoup(instream, 'html.parser')
            s.parse_station_name(tree)
            self.assertEqual(s.name, 'Pomona-Walnut Valley')
            s.parse_report_time(tree)
            last_update = datetime(2019, 7, 16, 20, 0)
            next_update = last_update + s._update_delay
            self.assertEqual(s.last_update, last_update)
            self.assertEqual(s.next_update, next_update)
            s.parse_aqi(tree)
            self.assertEqual(s.carbon_monoxide, 2)
            self.assertEqual(s.nitrogen_dioxide, 5)
            self.assertEqual(s.particulate_matter_10, 38)

    def test_async_update(self):
        c = sensor.CurrentAQI(4, None)
        self.assertEqual(c.last_update, datetime(1, 1, 1))
        self.assertEqual(c._name, None)
        with patch('scaqmd.sensor.async_fetch_state', new=fake_fetch_state):
            asyncio.run(c.async_update())
            self.assertEqual(c.last_update, datetime(2019, 7, 16, 20, 0))

    def test_async_no_update(self):
        with patch('scaqmd.sensor.async_fetch_state', new=fake_fetch_state), \
             patch('scaqmd.sensor.CurrentAQI.parse_aqi') as parse_aqi:
            c = sensor.CurrentAQI(4, None)
            c._last_update = datetime.now()
            c._next_update = datetime.now() + c._update_delay
            c._name = 'Pomona-Walnut Valley'
            asyncio.run(c.async_update())
            self.assertEqual(parse_aqi.called, False)


if __name__ == '__main__':
    main()
