"""
Support for the PyTTSX text-to-speech service.
"""
import logging
import os

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pyttsx3==2.7']

DOMAIN = 'tts_pyttsx3'

# ------
# Config
# ------

CONF_VOICE = 'voice'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_VOICE): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

# --------
# Services
# --------

SERVICE_SAY = 'say'
ATTR_MESSAGE = 'message'
ATTR_VOICE = 'voice'

SCHEMA_SERVICE_SAY = vol.Schema({
    vol.Required(ATTR_MESSAGE): cv.string,
    vol.Optional(ATTR_VOICE): cv.string
}, extra=vol.ALLOW_EXTRA)

def setup(hass, config):
    default_voice = config[DOMAIN].get(CONF_VOICE)

    # Create engine
    import pyttsx3
    engine = pyttsx3.init()

    if default_voice is None:
        default_voice = engine.getProperty('voice')

    def say(call):
        message = call.data[ATTR_MESSAGE]
        engine.setProperty('voice', default_voice)

        for name, value in call.data.items():
            if name != ATTR_MESSAGE:
                # Pass all additional properties into the engine
                engine.setProperty(name, value)

        engine.say(message)
        engine.runAndWait()

    hass.services.register(DOMAIN, SERVICE_SAY, say,
                           schema=SCHEMA_SERVICE_SAY)

    _LOGGER.info('Started')

    return True
