"""
Provide functionality to recognize intents with the rasa natural language understanding (NLU) library.
"""
import logging
import os
import asyncio
import threading

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.helpers import intent, config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['spacy==2.0.11', 'sklearn-crfsuite==0.3.6',
                'scikit-learn==0.19.1', 'rasa-nlu==0.12.3',
                'scipy==1.1.0']

DOMAIN = 'rasa_nlu'
DEFAULT_NAME = 'rasa_nlu'

# ------
# Config
# ------

# Path to directory where rasaNLU stores projects
CONF_PROJECT_DIR = 'project_dir'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_NAME, DEFAULT_NAME): cv.string,

        vol.Required(CONF_PROJECT_DIR): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

# --------
# Services
# --------

SERVICE_PARSE = 'parse'

# Text to parse
ATTR_MESSAGE = 'message'

# Name of project to use
ATTR_PROJECT_NAME = 'project'

SCHEMA_SERVICE_PARSE = vol.Schema({
    vol.Required(ATTR_MESSAGE): cv.string,
    vol.Required(ATTR_PROJECT_NAME): cv.string
})

OBJECT_RECOGNIZER = '%s.recognizer' % DOMAIN
STATE_IDLE = 'idle'
STATE_THINKING = 'thinking'

# Fired when an intent is recognized
EVENT_KNOWN_INTENT = 'known_intent'

# Fired when an intent is *not* recognized
EVENT_UNKNOWN_INTENT = 'unknown_intent'

# -----------------------------------------------------------------------------

class RasaIntentRecognizer(object):
    def __init__(self, name, hass, project_dir):
        self._name = name
        self._hass = hass
        self.logger = logging.getLogger(__name__)
        self._project_dir = project_dir
        self._projects = {}

    def parse(self, message, project_name):
        import rasa_nlu
        from rasa_nlu.project import Project
        self.logger.info('Parsing message with %s: %s' % (project_name, message))

        project = self._projects.get(project_name)
        if project is None:
            project = Project(project=project_name,
                              project_dir=self._project_dir)

            self._projects[project_name] = project

        # --------------------------
        # RasaNLU intent JSON format
        # --------------------------
        # {
        #   "intent": {
        #     "name": "...",
        #     "confidence": 1.0
        #   },
        #   "entities": [
        #     {
        #       "value": "...",
        #       "entity": "..."
        #     }
        #   ],
        #   "text": "..."
        # }
        result = project.parse(message)
        self.logger.debug(str(result))

        return result

@asyncio.coroutine
def async_setup(hass, config):
    name = config[DOMAIN].get(CONF_NAME, DEFAULT_NAME)
    project_dir = os.path.expanduser(config[DOMAIN][CONF_PROJECT_DIR])
    hass.data[DOMAIN] = RasaIntentRecognizer(name, hass, project_dir)

    # Passing these in manually with each state change since I don't know how
    # *not* overwrite them with nothing.
    state_attrs = {
        'friendly_name': 'Intent Recognizer',
        'icon': 'mdi:cogs',
        'intent': ''
    }

    @asyncio.coroutine
    def async_parse(call):
        message = call.data[ATTR_MESSAGE]
        project_name = call.data[ATTR_PROJECT_NAME]

        # idle -> thinking
        hass.states.async_set(OBJECT_RECOGNIZER, STATE_THINKING, state_attrs)

        # Run parsing in a separate thread
        result = {}
        parse_event = threading.Event()
        def parse():
            nonlocal result
            result = hass.data[DOMAIN].parse(message, project_name)
            parse_event.set()

        thread = threading.Thread(target=parse, daemon=True)
        thread.start()

        loop = asyncio.get_event_loop()
        yield from loop.run_in_executor(None, parse_event.wait)

        # Deconstruct result
        intent_type = ''
        if 'intent' in result:
            intent_type = result['intent']['name']
            slots = {}

            if 'entities' in result:
                # This will unfortunately only allow for one value per entity (slot).
                # rasaNLU supports multiple values per slot, but hass doesn't seem to.
                for entity_value in result['entities']:
                    slots[entity_value['entity']] = {
                        'value': entity_value['value']
                    }

            try:
                # Try to handle the intent with hass
                yield from intent.async_handle(
                    hass, DOMAIN, intent_type,
                    slots=slots, text_input=message)

                # Fire known intent event
                hass.bus.async_fire(EVENT_KNOWN_INTENT, {
                    'name': name,          # name of the component
                    'intent_type': intent_type,  # type of intent
                    'slots': slots,              # slots and values
                    'message': message           # text provided
                })
            except:
                # Fire unknown intent event
                hass.bus.async_fire(EVENT_UNKNOWN_INTENT, {
                    'name': name, # name of the component
                    'message': message  # text provided
                })

        state_attrs['intent'] = intent_type

        # thinking -> idle
        hass.states.async_set(OBJECT_RECOGNIZER, STATE_IDLE, state_attrs)

    # -> idle
    hass.states.async_set(OBJECT_RECOGNIZER, STATE_IDLE, state_attrs)
    hass.services.async_register(DOMAIN, SERVICE_PARSE, async_parse,
                                 schema=SCHEMA_SERVICE_PARSE)

    _LOGGER.info('Started')

    return True
