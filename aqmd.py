from collections import OrderedDict
from collections.abc import Mapping
import csv
from homeassistant.components.sensor import PLATFORM_SCHEMA
from homeassistant.helpers.entity import Entity
import homeassistant.helpers.config_validation as cv
import logging
import requests
import time
import voluptuous as vol

_LOGGER = logging.getLogger(__name__)

#REQUIREMENTS = ['dateutil==2.5.3']

DOMAIN = 'aqmd_sensor'

SCAQMD_CURRENT_CSV = 'https://opendata.arcgis.com/datasets/d50c7062e9024c68b22bd4f15710a7f6_0.csv'
SCAQMD_TOMORROW_CSV = 'https://opendata.arcgis.com/datasets/67b86d6bc8414fb6b977df2ed6e1e171_0.csv'

CONF_STATION = 'station'
CONF_FORECAST = 'forecast'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Optional('CONF_STATION'): cv.positive_int,
    vol.Optional('CONF_FORECAST'): cv.positive_int,
})

CURRENT_LABELS = ['sra', 'name', 'aqi', 'current_datetime',
                  'category_desc', 'pollutant_desc', 'link']
FORECAST_LABELS = ['sra', 'name', 'aqi', 'date', 'category_desc', 'pollutant_desc']

def setup_platform(hass, config, add_devices, discovery_info=None):
    devices = []
    _LOGGER.info("config: %s", str(config))
    if 'station' in config['aqmd']:
        #station = config['aqmd']['station']
        station = 8
        aqmd_current = AQMDCache(SCAQMD_CURRENT_CSV, True)
        devices.append(AQMDSensor(hass, aqmd_current, station, True))
    if 'forecast' in config['aqmd']:
        #station = config['aqmd']['forecast']
        station = 8
        aqmd_forecast = AQMDCache(SCAQMD_TOMORROW_CSV, False)
        devices.append(AQMDSensor(aqmd_forecast, station, False))
    add_devices(devices, True)

def parse_aqi_csv(text, labels):
    """Parse air quality csv into a dictionary of values.

    the first key is the station ID, the second keys are the
    data values for that station.
    """
    from dateutil.parser import parse

    data = csv.reader(text.split('\n'))
    header = next(data)
    columns = OrderedDict()
    for label in labels:
        columns[label] = header.index(label)

    results = {}
    for row in data:
        if len(row) > 0:
            parsed_row = {}
            for label in columns:
                if label in ('date', 'current_datetime'):
                    parsed_row[label] = parse(row[columns[label]])
                elif label in ('aqi', 'sra'):
                    parsed_row[label] = int(row[columns[label]])
                else:
                    parsed_row[label] = row[columns[label]]
            results[parsed_row['sra']] = parsed_row
    return results


class AQMDCache(Mapping):
    """Singleton object to cache requests to the OpenGIS API.
    """
    def __init__(self, url, is_current):
        self.url = url
        if is_current:
            self.labels = CURRENT_LABELS
            self.suffix = "Current Air Quality"
        else:
            self.labels = FORECAST_LABELS
            self.suffix = "Tomorrows Forecast Air Quality"
        self._current = None
        self.last_update = 0

    def update_aqi(self):
        """Update current information

        Website says its usually about 30 minutes after the hour
        """
        response = requests.get(self.url)
        self.current = parse_aqi_csv(response.text, self.labels)
        return self.current

    @property
    def current(self):
        if self._current is None:
            self.update_aqi()
        return self._current

    @current.setter
    def current(self, value):
        self.last_update = time.time()
        self._current = value
    
    def __getitem__(self, key):
        return self.current[key]

    def __iter__(self):
        return iter(self.current)

    def __len__(self):
        return len(self.current)


class AQMDSensor(Entity):
    """Read air quality information from AQMD website.
    """
    def __init__(self, aqmd_cache, station_id, timeout=3600):
        """Initialize the sensor"""
        self.aqmd_cache = aqmd_cache
        self._previous_aqi = None
        self._previous_category = None
        self.station_id = station_id
        self.timeout = timeout

    @property
    def aqi(self):
        return self.aqmd_cache[self.station_id]['aqi']

    @property
    def category(self):
        return self.aqmd_cache[self.station_id]['current_desc']

    @property
    def pollutant(self):
        return self.aqmd_cache[self.station_id]['pollutant_desc']

    @property
    def name(self):
        """Return the name of this sensor"""
        location_name = self.aqmd_cache[self.station_id]['name']
        return location_name + ' ' + self.aqmd_cache.suffix

    @property
    def state(self):
        """Return the state of the sensor"""
        return self.aqi

    def unit_of_measurement(self):
        """Return the unit of measurement

        air quality indicator is untyped.
        """
        return self.category

    def update(self):
        """Fetch new state data for the sensor
        """
        if time.time() > self.aqmd_cache.last_update + self.timeout:
            self.aqmd_cache.update()

            if self.aqi != self._previous_aqi:
                self.hass.bus.fire('aqi_changed', {
                    'previous_aqi': self._previous_aqi,
                    'aqi': self.aqi})
            if self.category != self._previous_category:
                self.hass.bus.fire('category_changed', {
                    'previous_category': self._previous_category,
                    'category': self.category})
            self._previous_aqi = self.aqi
            self._previous_category = self.category


if __name__ == '__main__':
    sensor = AQMDSensor(aqmd_current, 8)
    print(sensor.name)
    print(sensor.state)
