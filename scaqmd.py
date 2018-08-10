"""Sensor to interact with SCAQMD Air quality open data
(South Coast Air Quality Management District)

See https://data-scaqmd-online.opendata.arcgis.com/ for more information

SCAQMD Hourly forecast is updated on the hour.
SCAQMD Forecast is available daily at about noon
"""


from collections import namedtuple
from collections.abc import MutableMapping
import csv
from datetime import datetime, timedelta
from homeassistant.const import (
    ATTR_ATTRIBUTION,
    ATTR_NAME,
    ATTR_DATE,
)
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
from homeassistant.util import Throttle
from homeassistant.util import dt
import logging
import requests
import time
import voluptuous as vol
import pytz

_LOGGER = logging.getLogger(__name__)

#REQUIREMENTS = ['dateutil==2.5.3']

ATTR_AQI = 'aqi'
ATTR_CURRENT_TIME = 'datetime'
ATTR_CATEGORY = 'category'
ATTR_POLLUTANT = 'pollutant'
ATTR_URL = 'link'

CONF_STATION = 'station'
CONF_MODE = 'mode'
CONF_CURRENT_URL = 'current_url'
CONF_FORECAST_URL = 'forecast_url'

MODES = ['current', 'forecast']

DEFAULT_MODE = 'current'
DEFAULT_CURRENT_URL = 'https://opendata.arcgis.com/datasets/d50c7062e9024c68b22bd4f15710a7f6_0.csv'
DEFAULT_FORECAST_URL = 'https://opendata.arcgis.com/datasets/67b86d6bc8414fb6b977df2ed6e1e171_0.csv'

DEFAULT_TIMEZONE = pytz.timezone('America/Los_Angeles')

MIN_TIME_BETWEEN_UPDATES = timedelta(minutes=10)

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STATION): cv.string,
    vol.Optional(CONF_MODE, default=DEFAULT_MODE): vol.All(vol.In(MODES)),
    vol.Optional(CONF_CURRENT_URL, default=DEFAULT_CURRENT_URL): cv.url,
    vol.Optional(CONF_FORECAST_URL, default=DEFAULT_FORECAST_URL): cv.url,
})


def parse_aqi_csv(text: bytes):
    """Parse air quality csv into a dictionary of values.

    the first key is the station ID, the second keys are the
    data values for that station.
    """
    data = csv.reader(text.decode('utf-8-sig').strip().split('\n'))
    columns = next(data)

    results = {}
    for row in data:
        if len(row) > 0:
            parsed_row = {}
            for name, value in zip(columns, row):
                if name == 'current_datetime':
                    parsed_row[name] = dt.parse_datetime(value)
                elif name == 'date':
                    value = datetime.strptime(value, '%m/%d/%Y')
                    value = DEFAULT_TIMEZONE.localize(value)
                    parsed_row[name] = value
                elif name in ('aqi', 'sra'):
                    parsed_row[name] = int(value)
                elif name in ('Shape__Area', 'Shape__Length'):
                    # skip geo polygon
                    pass
                else:
                    parsed_row[name] = value
            results[parsed_row['sra']] = parsed_row
    return results


SCAQMDFile = namedtuple('SCAQMDFile', ['table', 'is_current', 'last_updated', 'valid_timestamp'])


class SCAQMDCache(MutableMapping):
    """Singleton object to cache requests to the OpenGIS API.
    """
    def __init__(self):
        self._cache = {}

    def _update_aqi(self, url: str):
        """Update current information

        Website says its usually about 30 minutes after the hour
        """
        response = requests.get(url)
        self[url] = response.content

    def __getitem__(self, key):
        if key not in self._cache:
            self._update_aqi(key)

        return self._cache[key]

    def __setitem__(self, key, value):
        table = parse_aqi_csv(value)
        first = table[next(iter(table.keys()))]
        is_current = 'current_datetime' in first
        if is_current:
            timestamp = first['current_datetime']
        else:
            timestamp = first['date']

        self._cache[key] = SCAQMDFile(
            table,
            is_current,
            time.time(),
            timestamp)

    def __delitem__(self, key):
        del self._cache[key]

    def __iter__(self):
        return iter(self._cache)

    def __len__(self):
        return len(self._cache)


class SCAQMDSensor(Entity):
    """Read air quality information from SCAQMD website.
    """
    ICON = 'mdi:cloud-outline'

    def __init__(self, hass, url, station_id, timeout=3600, scaqmd_cache=None):
        """Initialize the sensor"""
        self._hass = hass
        self._url = url
        self._station_id = int(station_id)
        self._scaqmd_cache = scaqmd_cache if scaqmd_cache else SCAQMDCache()
        self._previous_aqi = None
        self._previous_category = None
        self._timeout = timeout

    @property
    def station(self):
        scaqmddata = self._scaqmd_cache[self._url]
        return scaqmddata.table.get(self._station_id)

    @property
    def is_current(self):
        scaqmddata = self._scaqmd_cache[self._url]
        return scaqmddata.is_current

    @property
    def state_attributes(self):
        attributes = {
            ATTR_ATTRIBUTION: 'SCSCAQMD Open Data',
            ATTR_NAME: self.name,
            ATTR_DATE: self.valid_timestamp,
            ATTR_AQI: self.station['aqi'],
            ATTR_CATEGORY: self.station['category_desc'],
            ATTR_POLLUTANT: self.station['pollutant_desc'],
        }
        #if self.is_current:
        #    attributes[ATTR_URL] = self.link
        return attributes

    @property
    def icon(self):
        return self.ICON

    @property
    def name(self):
        """Return the name of this sensor"""
        if self.is_current:
            suffix = "Current Air Quality"
        else:
            suffix = "Tomorrows Forecast Air Quality"
        location_name = self.station.get('name', 'Undefined')
        return location_name + ' ' + suffix

    @property
    def state(self):
        """Return the state of the sensor"""
        return self.station['aqi']

    @property
    def unit_of_measurement(self):
        """Return the unit of measurement of this entity, if any."""
        return 'AQI'

    @property
    def next_update(self):
        scaqmddata = self._scaqmd_cache[self._url]
        t = scaqmddata.valid_timestamp
        if self.is_current:
            # updated hourly with data from each station
            return datetime(t.year, t.month, t.day, t.hour + 1, tzinfo=pytz.utc)
        else:
            # available daily at about noon
            value = datetime(t.year, t.month, t.day, 12, 0)
            value = DEFAULT_TIMEZONE.localize(value)
            value = value.astimezone(pytz.utc)
            return value

    @Throttle(MIN_TIME_BETWEEN_UPDATES)
    def update(self):
        """Fetch new state data for the sensor
        """
        if datetime.now(pytz.utc) > self.next_update:
            self._scaqmd_cache._update_aqi(self._url)

    @property
    def valid_timestamp(self):
        return self._scaqmd_cache[self._url].valid_timestamp


scaqmd_cache_singleton = SCAQMDCache()


def setup_platform(hass, config, add_devices, discovery_info=None):
    station = config.get(CONF_STATION)
    mode = config.get(CONF_MODE, 'current')
    current_url = config.get(CONF_CURRENT_URL, DEFAULT_CURRENT_URL)
    forecast_url = config.get(CONF_FORECAST_URL, DEFAULT_FORECAST_URL)

    _LOGGER.info("SCAQMD platform station: %s", str(station))
    if mode == 'current':
        url = current_url
    else:
        url = forecast_url
    device = SCAQMDSensor(hass, url, station, scaqmd_cache=scaqmd_cache_singleton)
    add_devices([device], True)

    return True


if __name__ == '__main__':
    from argparse import ArgumentParser
    from dateutil.tz import tzlocal
    parser = ArgumentParser()
    parser.add_argument('station_id', type=int)
    args = parser.parse_args()
    sensor = SCAQMDSensor(DEFAULT_CURRENT_URL, args.station_id)
    print(sensor.name)
    print("Date :", sensor.date.astimezone(tzlocal()))
    print("State:", sensor.state)
