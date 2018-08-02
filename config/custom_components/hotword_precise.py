"""
Provide functionality to listen for a hot/wake word from mycroft-precise.
"""
import logging
import os
import asyncio
import threading

import voluptuous as vol

from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import intent, config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['mycroft-precise==0.2.0', 'precise-runner==0.2.1']

DOMAIN = 'hotword_precise'

# ------
# Config
# ------

# Path to the Mycroft Precise hotword model file (.pb)
CONF_MODEL = 'model'

# From 0.0 to 1.0, relates to the network output level required to consider a
# chunk "active".
CONF_SENSITIVITY = 'sensitivity'

# Number of chunk activations needed to trigger on_activation.
# Higher values add latency but reduce false positives.
CONF_TRIGGER_LEVEL = 'trigger_level'

# ----------------------
# Configuration defaults
# ----------------------

DEFAULT_NAME = 'hotword_precise'
DEFAULT_SENSITIVITY = 0.5
DEFAULT_TRIGGER_LEVEL = 3

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_NAME, DEFAULT_NAME): cv.string,

        vol.Required(CONF_MODEL): cv.string,
        vol.Optional(CONF_SENSITIVITY, DEFAULT_SENSITIVITY): float,
        vol.Optional(CONF_TRIGGER_LEVEL, DEFAULT_TRIGGER_LEVEL): int
    })
}, extra=vol.ALLOW_EXTRA)

# --------
# Services
# --------

SERVICE_LISTEN = 'listen'

# Represents the hotword detector
OBJECT_DECODER = '%s.decoder' % DOMAIN

# Not doing anything
STATE_IDLE = 'idle'

# Listening for the hotword
STATE_LISTENING = 'listening'

# Fired when the hotword is detected
EVENT_HOTWORD_DETECTED = 'hotword_detected'

# -----------------------------------------------------------------------------

@asyncio.coroutine
def async_setup(hass, config):
    from precise_runner import PreciseEngine, PreciseRunner

    name = config[DOMAIN].get(CONF_NAME, DEFAULT_NAME)
    model = os.path.expanduser(config[DOMAIN].get(CONF_MODEL))
    sensitivity = config[DOMAIN].get(CONF_SENSITIVITY, DEFAULT_SENSITIVITY)
    trigger_level = config[DOMAIN].get(CONF_TRIGGER_LEVEL, DEFAULT_TRIGGER_LEVEL)

    state_attrs = {
        'friendly_name': 'Hotword',
        'icon': 'mdi:microphone'
    }

    assert os.path.exists(model), 'Model does not exist'
    runner = None
    terminated = False
    detected_event = threading.Event()

    @asyncio.coroutine
    def async_listen(call):
        nonlocal runner, detected_event

        hass.states.async_set(OBJECT_DECODER, STATE_LISTENING, state_attrs)

        engine = PreciseEngine('precise-engine', model)
        runner = PreciseRunner(engine,
                               sensitivity=sensitivity,
                               trigger_level=trigger_level,
                               on_activation=lambda: detected_event.set())


        # Runs in a separate thread
        detected_event.clear()
        runner.start()
        yield from asyncio.get_event_loop().run_in_executor(None, detected_event.wait)

        if not terminated:
            runner.stop()
            runner = None

            hass.states.async_set(OBJECT_DECODER, STATE_IDLE, state_attrs)

            # Fire detected event
            hass.bus.async_fire(EVENT_HOTWORD_DETECTED, {
                'name': name,       # name of the component
                'model': model      # model used
            })

    hass.services.async_register(DOMAIN, SERVICE_LISTEN, async_listen)
    hass.states.async_set(OBJECT_DECODER, STATE_IDLE, state_attrs)

    # Make sure the runner terminates property when home assistant stops
    @asyncio.coroutine
    def async_terminate(event):
        nonlocal runner, detected_event, terminated
        terminated = True

        if runner is not None:
            runner.stop()
            runner = None

        detected_event.set()

    hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, async_terminate)

    _LOGGER.info('Started')

    return True
