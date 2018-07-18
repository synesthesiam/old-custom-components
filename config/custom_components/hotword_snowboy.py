"""
Provide functionality to listen for a hot/wake word from snowboy.
"""
import logging
import os
import asyncio
import threading

import voluptuous as vol

from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import intent, config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['snowboy==1.2.0b1']

DOMAIN = 'hotword_snowboy'

# ------
# Config
# ------

CONF_MODEL = 'model'
CONF_SENSITIVITY = 'sensitivity'
CONF_AUDIO_GAIN = 'audio_gain'

DEFAULT_NAME = 'hotword_snowboy'
DEFAULT_SENSITIVITY = 0.5
DEFAULT_AUDIO_GAIN = 1.0

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_NAME, DEFAULT_NAME): cv.string,

        vol.Required(CONF_MODEL): cv.string,
        vol.Optional(CONF_SENSITIVITY, DEFAULT_SENSITIVITY): float,
        vol.Optional(CONF_AUDIO_GAIN, DEFAULT_AUDIO_GAIN): float
    })
}, extra=vol.ALLOW_EXTRA)

# --------
# Services
# --------

SERVICE_LISTEN = 'listen'

OBJECT_SNOWBOY = '%s.snowboy' % DOMAIN
STATE_IDLE = 'idle'
STATE_LISTENING = 'listening'

EVENT_HOTWORD_DETECTED = 'hotword_detected'

# -----------------------------------------------------------------------------

@asyncio.coroutine
def async_setup(hass, config):
    name = config[DOMAIN].get(CONF_NAME, DEFAULT_NAME)
    model = os.path.expanduser(config[DOMAIN].get(CONF_MODEL))
    sensitivity = config[DOMAIN].get(CONF_SENSITIVITY, DEFAULT_SENSITIVITY)
    audio_gain = config[DOMAIN].get(CONF_AUDIO_GAIN, DEFAULT_AUDIO_GAIN)

    assert os.path.exists(model), 'Model does not exist'
    detector = None
    terminated = False
    detected_event = threading.Event()

    @asyncio.coroutine
    def async_listen(call):
        nonlocal detector, detected_event
        from snowboy import snowboydecoder
        detector = snowboydecoder.HotwordDetector(
            model, sensitivity=sensitivity, audio_gain=audio_gain)

        def detect():
            detector.start(lambda: detected_event.set())

        # Run detector in a separate thread
        thread = threading.Thread(target=detect, daemon=True)
        hass.states.async_set(OBJECT_SNOWBOY, STATE_LISTENING)

        thread.start()
        yield from asyncio.get_event_loop().run_in_executor(None, detected_event.wait)

        if not terminated:
            detector.terminate()
            detector = None

            thread.join()

            hass.states.async_set(OBJECT_SNOWBOY, STATE_IDLE)

            # Fire detected event
            hass.bus.async_fire(EVENT_HOTWORD_DETECTED, {
                'name': name,       # name of the component
                'model': model      # model used
            })

    hass.services.async_register(DOMAIN, SERVICE_LISTEN, async_listen)
    hass.states.async_set(OBJECT_SNOWBOY, STATE_IDLE)

    # Make sure snowboy terminates property when home assistant stops
    @asyncio.coroutine
    def async_terminate(event):
        nonlocal detector, detected_event, terminated
        terminated = True

        if detector is not None:
            detector.terminate()
            detector = None

        detected_event.set()

    hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, async_terminate)

    _LOGGER.info('Started')

    return True
