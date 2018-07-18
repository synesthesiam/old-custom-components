"""
Provides functionality for using the pico text-to-speech system with results played through aplay.
"""
import logging
import os
import shutil
import subprocess
import tempfile

import voluptuous as vol

from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

DOMAIN = 'picotts_aplay'

# --------
# Services
# --------

SERVICE_SAY = 'say'
ATTR_MESSAGE = 'message'
ATTR_LANGUAGE = 'language'

SCHEMA_SERVICE_SAY = vol.Schema({
    vol.Required(ATTR_MESSAGE): cv.string
}, extra=vol.ALLOW_EXTRA)

def setup(hass, config):
    if shutil.which('pico2wave') is None:
        _LOGGER.error("'pico2wave' command not found")
        return False

    if shutil.which('aplay') is None:
        _LOGGER.error("'aplay' command not found")
        return False

    def say(call):
        message = call.data[ATTR_MESSAGE]
        language = call.data.get(ATTR_LANGUAGE, 'en-US')
        with tempfile.NamedTemporaryFile(suffix='.wav', mode='wb+') as wav_file:
            subprocess.check_call(['pico2wave',
                                   '-w', wav_file.name,
                                   '-l', language,
                                   message])
            wav_file.seek(0)

            aplay_args = ['aplay', '-q']
            for name, value in call.data.items():
                if name not in [ATTR_MESSAGE, ATTR_LANGUAGE]:
                    # Pass all additional properties as command-line arguments to aplay
                    args.extend(['-%s' % name, value])

            aplay_args.append(wav_file.name)
            subprocess.run(aplay_args)

    hass.services.register(DOMAIN, SERVICE_SAY, say,
                           schema=SCHEMA_SERVICE_SAY)

    _LOGGER.info('Started')

    return True
