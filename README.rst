Introduction
------------

This is a small web sensor to poll the California South Coast Air
Quality Management Districits `OpenData`_ feed for current and forecast
air quality.

Installation
------------

It is currently implemented as a custom sensor. You need to add the
scaqmd.py file (or a symlink to the file) to your homeassistant
configuration directory in the custom_components/sensors/ directory

Usage
-----

To enable the sensor you need to add it to your ``sensors`` block.
as a platform.

The most important option is ``station`` which is the numeric ID for the
SC AQMD region you're interested in. The `Current Air Quality Map`_
shows the regions with their numeric IDs.

For instance Long Beach is in region 4.

The next option is the ``mode`` flag

The default is ``current`` for a sensor that is reporting the current
AQI reading for this hour.

``mode: forecast`` will return tomorrows AQI forecast.

``current_url`` and ``forecast_url`` allow overriding the arggis open
dataset urls, but I don't expect overriding them will be that useful
since the other air quality districts seem to format their data
differently.

Usage Example
-------------

Here is a complete configuration showing the current and forecast
conditions for Long Beach

.. code::

    sensors:
        - platform: scaqmd
          station: 4
        - platform: scaqmd
          station: 4
          mode: forecast

.. _OpenData: https://data-scaqmd-online.opendata.arcgis.com/
.. _Current Air Quality Map: https://data-scaqmd-online.opendata.arcgis.com/datasets/7326e61dda654f5c8a0a0218ff4ac2c8
