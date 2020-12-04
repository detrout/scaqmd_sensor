"""Sensor for checking the air quality around southern california"""
import logging

import voluptuous as vol

import homeassistant.helpers.config_validation as cv
from homeassistant.components.air_quality import (
    AirQualityEntity,
    PLATFORM_SCHEMA,
)

from homeassistant.helpers.aiohttp_client import async_get_clientsession

import aiohttp
import datetime
from bs4 import BeautifulSoup

_LOGGER = logging.getLogger(__name__)

ATTRIBUTION = "Air quality from https://aqmd.gov"

CONF_STATION = 'station'

PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend({
    vol.Required(CONF_STATION): cv.string,
})


async def async_setup_platform(hass, config, async_add_entities,
                               discovery_info=None):
    """Setup the South Coast Air Quality Sensor"""
    location = config.get(CONF_STATION)

    async_add_entities(
        [CurrentAQI(location, async_get_clientsession(hass))],
        True
    )


class CurrentAQI(AirQualityEntity):
    """Representation of a South Coast AQMD monitoring region"""
    CURRENT_AQI = 'https://xappprod.aqmd.gov/aqdetail/AirQuality?AreaNumber={area}'

    def __init__(self, number, session):
        self._last_update = datetime.datetime(1, 1, 1)
        self._next_update = datetime.datetime(1, 1, 1)
        self._update_delay = datetime.timedelta(seconds=4000)
        self._backoff_delay = datetime.timedelta(seconds=500)
        self._name = None
        self._number = number
        self._session = session

        self._carbon_monoxide = None
        self._nitrogen_dioxide = None
        self._ozone = None
        self._particulate_matter_2_5 = None
        self._particulate_matter_10 = None

    async def async_update(self) -> None:
        """Retrieve latest state."""
        next_update_cache = self.next_update
        if datetime.datetime.now() > self.next_update:
            url = CurrentAQI.CURRENT_AQI.format(area=self._number)
            _LOGGER.info('Requesting: %s', url)
            text = await async_fetch_state(self._session, url)
            tree = BeautifulSoup(text, 'html.parser')
            self.parse_report_time(tree)
            self.parse_aqi(tree)
            if self.next_update == next_update_cache:
                # page wasn't updated
                self._next_update += self._backoff_delay
            print('Update called: cache {} next {} last {}'.format(
                next_update_cache,
                self.next_update,
                self.last_update))
            if self._name is None:
                self.parse_station_name(tree)

    @property
    def last_update(self) -> datetime.datetime:
        return self._last_update

    @property
    def next_update(self) -> datetime.datetime:
        return self._next_update

    @property
    def attribution(self) -> str:
        return ATTRIBUTION

    @property
    def air_quality_index(self) -> int:
        aqi = []
        for attrib in [
                self.carbon_monoxide,
                self.nitrogen_dioxide,
                self.ozone,
                self._particulate_matter_2_5,
                self._particulate_matter_10,
        ]:
            if attrib is not None:
                aqi.append(attrib)

        if len(aqi) > 0:
            return max(aqi)

    @property
    def carbon_monoxide(self) -> int:
        """Return the CO (carbon monoxide) level."""
        return self._carbon_monoxide

    @carbon_monoxide.setter
    def carbon_monoxide(self, value: int):
        self._carbon_monoxide = value

    @property
    def name(self) -> str:
        """Return the name of the sensor."""
        return self._name

    @property
    def nitrogen_dioxide(self) -> int:
        """Return the NO2 (nitrogen dioxide) level."""
        return self._nitrogen_dioxide

    @nitrogen_dioxide.setter
    def nitrogen_dioxide(self, value: int):
        self._nitrogen_dioxide = value

    @property
    def ozone(self) -> int:
        """Return the O3 (ozone) level."""
        return self._ozone

    @ozone.setter
    def ozone(self, value: int):
        self._ozone = value

    @property
    def particulate_matter_2_5(self):
        """Return the particulate matter 2.5 level."""
        return self._particulate_matter_2_5

    @particulate_matter_2_5.setter
    def particulate_matter_2_5(self, value: int):
        self._particulate_matter_2_5 = value

    @property
    def particulate_matter_10(self):
        """Return the particulate matter 10 level."""
        return self._particulate_matter_10

    @particulate_matter_10.setter
    def particulate_matter_10(self, value: int):
        self._particulate_matter_10 = value

    def parse_aqi(self, tree: BeautifulSoup):
        """Parse AQI tree
        """
        setters = {
            'O3': 'ozone',
            'PM2.5': 'particulate_matter_2_5',
            'PM10': 'particulate_matter_10',
            'NO2': 'nitrogen_dioxide',
            'CO': 'carbon_monoxide',
        }
        header = None
        values = []
        table = tree.find_all('table')[1]
        for row in table.find_all('tr')[1:]:
            parsed_row = []
            for element in row.find_all('td'):
                text = element.text.strip()
                if len(text) > 0:
                    parsed_row.append(text)
            try:
                value = int(parsed_row[1])
            except ValueError as e:
                _LOGGER.warn('Invalid AQI %s. %s', str(e), parsed_row)
            attr_name = setters.get(parsed_row[0])
            if attr_name is not None:
                self.__setattr__(attr_name, value)

    def parse_station_name(self, tree: BeautifulSoup):
        div = tree.find('div', attrs={'class': 'p20'})
        station_label = div.find('label')
        if station_label.text == 'Station Name:':
            station_name = station_label.next_sibling
            self._name = station_name.strip()

    def parse_report_time(self, tree: BeautifulSoup):
        div = tree.find('div', attrs={'class': 'p20'})
        for label in div.find_all('label'):
            if 'Reading Date Time' in label.text:
                time_label = label.text.split(': ')
                if len(time_label) == 2:
                    time_content = time_label[1]
                    time_text = time_content[:time_content.index('m')+1].strip()
                    ts = datetime.datetime.strptime(time_text, '%m/%d/%Y %I:%M%p')
                    self._last_update = ts
                    self._next_update = ts + self._update_delay

    @property
    def state_attributes(self):
        data = super().state_attributes
        return data

    @property
    def state(self) -> int:
        return self.air_quality_index

    @property
    def unit_of_measurement(self):
        return 'AQI'


async def async_fetch_state(session, url):
    async with session.get(url) as response:
        return await response.text()


async def main():
    area = 8
    async with aiohttp.ClientSession() as session:
        aqi = CurrentAQI(area, session)
        await aqi.async_update()

if __name__ == '__main__':
    import asyncio
    loop = asyncio.get_event_loop()
    loop.run_until_complete(main())
