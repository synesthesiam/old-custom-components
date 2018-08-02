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

# Path to the snowboy hotword model file (.umdl or .pmdl)
CONF_MODEL = 'model'

# Sensitivity of detection (defaults to 0.5).
# Ranges from 0-1.
CONF_SENSITIVITY = 'sensitivity'

# Amount of audio gain when recording (defaults to 1.0)
CONF_AUDIO_GAIN = 'audio_gain'

# ----------------------
# Configuration defaults
# ----------------------

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

# Represents the hotword detector
OBJECT_SNOWBOY = '%s.decoder' % DOMAIN

# Not doing anything
STATE_IDLE = 'idle'

# Listening for the hotword
STATE_LISTENING = 'listening'

# Fired when the hotword is detected
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

    state_attrs = {
        'friendly_name': 'Hotword',
        'icon': 'mdi:microphone'
    }

    @asyncio.coroutine
    def async_listen(call):
        nonlocal detected_event, terminated
        from snowboy import snowboydecoder

        interrupted = False

        def interrupt_callback():
            nonlocal interrupted, terminated
            return interrupted or terminated

        def detect():
            detector = snowboydecoder.HotwordDetector(
                model, sensitivity=sensitivity, audio_gain=audio_gain)

            detector.start(lambda: detected_event.set(),
                           interrupt_check=interrupt_callback,
                           sleep_time=0.03)

            detector.terminate()

        # Run detector in a separate thread
        detected_event.clear()
        thread = threading.Thread(target=detect, daemon=True)
        hass.states.async_set(OBJECT_SNOWBOY, STATE_LISTENING, state_attrs)

        thread.start()
        yield from asyncio.get_event_loop().run_in_executor(None, detected_event.wait)
        interrupted = True

        if not terminated:
            hass.states.async_set(OBJECT_SNOWBOY, STATE_IDLE, state_attrs)

            # Fire detected event
            hass.bus.async_fire(EVENT_HOTWORD_DETECTED, {
                'name': name,       # name of the component
                'model': model      # model used
            })

    hass.services.async_register(DOMAIN, SERVICE_LISTEN, async_listen)
    hass.states.async_set(OBJECT_SNOWBOY, STATE_IDLE, state_attrs)

    # Make sure snowboy terminates property when home assistant stops
    @asyncio.coroutine
    def async_terminate(event):
        nonlocal terminated
        terminated = True
        detected_event.set()

    hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, async_terminate)

    _LOGGER.info('Started')

    return True
