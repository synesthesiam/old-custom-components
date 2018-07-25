"""
Provide functionality to listen for commands from a microphone with PyAudio and webrtcvad.
"""
import logging
import os
import math
import asyncio
import wave
import threading
import requests
import io

import voluptuous as vol

from homeassistant.const import CONF_NAME
from homeassistant.helpers import intent, config_validation as cv

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['PyAudio==0.2.8', 'webrtcvad==2.0.10']

DOMAIN = 'command_listener'

# ------
# Config
# ------

CONF_DEVICE_INDEX = 'device_index'
CONF_SAMPLE_RATE = 'sample_rate'
CONF_SAMPLE_WIDTH = 'sample_width'
CONF_CHANNELS = 'channels'
CONF_CHUNK_SIZE = 'chunk_size'

CONF_VAD_MODE = 'vad_mode'

CONF_MIN_SEC = 'min_sec'
CONF_SILENCE_SEC = 'silence_sec'
CONF_TIMEOUT_SEC = 'timeout_sec'

# URL to POST recorded WAV data to
CONF_URL = 'url'

DEFAULT_NAME = 'command_listener'
DEFAULT_DEVICE_INDEX = -1    # default microphone
DEFAULT_SAMPLE_RATE = 16000  # 16Khz
DEFAULT_SAMPLE_WIDTH = 2     # 16-bit
DEFAULT_CHANNELS = 1         # mono
DEFAULT_CHUNK_SIZE = 480     # 30 ms

DEFAULT_VAD_MODE = 0         # 0-3 (agressiveness)

DEFAULT_MIN_SEC = 2.0        # min seconds that command must last
DEFAULT_SILENCE_SEC = 0.5    # min seconds of silence after command
DEFAULT_TIMEOUT_SEC = 30.0   # max seconds that command can last

DEFAULT_URL = None           # Use URL from service request

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_NAME, DEFAULT_NAME): cv.string,

        vol.Optional(CONF_DEVICE_INDEX, DEFAULT_DEVICE_INDEX): int,
        vol.Optional(CONF_SAMPLE_RATE, DEFAULT_SAMPLE_RATE): int,
        vol.Optional(CONF_SAMPLE_WIDTH, DEFAULT_SAMPLE_WIDTH): int,
        vol.Optional(CONF_CHANNELS, DEFAULT_CHANNELS): int,
        vol.Optional(CONF_CHUNK_SIZE, DEFAULT_CHUNK_SIZE): int,

        vol.Optional(CONF_VAD_MODE, DEFAULT_VAD_MODE): int,
        vol.Optional(CONF_MIN_SEC, DEFAULT_MIN_SEC): float,
        vol.Optional(CONF_SILENCE_SEC, DEFAULT_SILENCE_SEC): float,
        vol.Optional(CONF_TIMEOUT_SEC, DEFAULT_TIMEOUT_SEC): float,

        vol.Optional(CONF_URL, DEFAULT_URL): cv.string
    })
}, extra=vol.ALLOW_EXTRA)

# --------
# Services
# --------

SERVICE_LISTEN = 'listen'

ATTR_FILENAME = 'filename'
ATTR_URL = 'url'

SCHEMA_SERVICE_LISTEN = vol.Schema({
    vol.Optional(ATTR_FILENAME): cv.string,
    vol.Optional(ATTR_URL): cv.string
})

OBJECT_MICROPHONE = '%s.microphone' % DOMAIN
STATE_IDLE = 'idle'
STATE_RECORDING = 'recording'

EVENT_SPEECH_RECORDED = 'speech_recorded'

class CommandListener(object):
    import pyaudio
    import webrtcvad

    def __init__(self, device_index, sample_rate, sample_width, channels,
                 chunk_size, vad_mode, min_sec, silence_sec, timeout_sec):
        self._logger = logging.getLogger(__name__)

        self._device_index = device_index
        self._sample_rate = sample_rate
        self._sample_width = sample_width
        self._channels = channels
        self._chunk_size = chunk_size

        self._vad_mode = vad_mode
        self._min_sec = min_sec
        self._silence_sec = silence_sec
        self._timeout_sec = timeout_sec

        self._seconds_per_buffer = self._chunk_size / self._sample_rate
        self._max_buffers = int(math.ceil(self._timeout_sec / self._seconds_per_buffer))

        self._vad = None
        self._audio = None

    @asyncio.coroutine
    def async_listen(self, filename=None, url=None):
        import pyaudio

        if self._vad is None:
            import webrtcvad
            self._vad = webrtcvad.Vad()
            self._vad.set_mode(self._vad_mode)

        recorded_data = []
        finished_event = threading.Event()

        # Recording state
        max_buffers = int(math.ceil(self._timeout_sec / self._seconds_per_buffer))
        silence_buffers = int(math.ceil(self._silence_sec / self._seconds_per_buffer))
        min_phrase_buffers = int(math.ceil(self._min_sec / self._seconds_per_buffer))
        in_phrase = False
        after_phrase = False
        finished = False

        # PyAudio callback function
        def stream_callback(data, frame_count, time_info, status):
            nonlocal max_buffers, silence_buffers, min_phrase_buffers
            nonlocal in_phrase, after_phrase
            nonlocal recorded_data, finished

            # Check maximum number of seconds to record
            max_buffers -= 1
            if max_buffers <= 0:
                # Timeout
                finished = True

                # Reset
                in_phrase = False
                after_phrase = False

            # Detect speech in chunk
            is_speech = self._vad.is_speech(data, self._sample_rate)
            if is_speech and not in_phrase:
                # Start of phrase
                in_phrase = True
                after_phrase = False
                recorded_data = data
                min_phrase_buffers = int(math.ceil(self._min_sec / self._seconds_per_buffer))
            elif in_phrase and (min_phrase_buffers > 0):
                # In phrase, before minimum seconds
                recorded_data += data
                min_phrase_buffers -= 1
            elif in_phrase and is_speech:
                # In phrase, after minimum seconds
                recorded_data += data
            elif not is_speech:
                # Outside of speech
                if after_phrase and (silence_buffers > 0):
                    # After phrase, before stop
                    recorded_data += data
                    silence_buffers -= 1
                elif after_phrase and (silence_buffers <= 0):
                    # Phrase complete
                    recorded_data += data
                    finished = True

                    # Reset
                    in_phrase = False
                    after_phrase = False
                elif in_phrase and (min_phrase_buffers <= 0):
                    # Transition to after phrase
                    after_phrase = True
                    silence_buffers = int(math.ceil(self._silence_sec / self._seconds_per_buffer))

            if finished:
                finished_event.set()

            return (data, pyaudio.paContinue)

        # -----------------------------------------------------------------

        # Open microphone device
        audio = pyaudio.PyAudio()
        device_index = None
        if self._device_index >= 0:
            device_index = self._device_index

        data_format = pyaudio.get_format_from_width(self._sample_width)

        mic = audio.open(format=data_format,
                            channels=self._channels,
                            rate=self._sample_rate,
                            input_device_index=device_index,
                            input=True,
                            stream_callback=stream_callback,
                            frames_per_buffer=self._chunk_size)

        loop = asyncio.get_event_loop()
        # Start listening
        self._logger.debug('Listening')
        mic.start_stream()

        yield from loop.run_in_executor(None, finished_event.wait)

        # Stop listening and clean up
        mic.stop_stream()
        mic.close()
        audio.terminate()

        self._logger.debug('Stopped listening')
        self._logger.info('Recorded %s byte(s) of audio' % len(recorded_data))

        if filename is not None:
            # Write WAV data to file system
            with wave.open(filename, mode='wb') as wav_file:
                wav_file.setframerate(self._sample_rate)
                wav_file.setsampwidth(self._sample_width)
                wav_file.setnchannels(self._channels)
                wav_file.writeframesraw(recorded_data)
        elif url is not None:
            # POST WAV data to URL
            with io.BytesIO() as wav_data:
                with wave.open(wav_data, mode='wb') as wav_file:
                    wav_file.setframerate(self._sample_rate)
                    wav_file.setsampwidth(self._sample_width)
                    wav_file.setnchannels(self._channels)
                    wav_file.writeframesraw(recorded_data)

                wav_data.seek(0)
                requests.post(url, data=wav_data,
                              headers={ 'Content-Type': 'audio/wav' },
                              timeout=10)

                self._logger.debug('POSTed %s byte(s) to' % url)

# -----------------------------------------------------------------------------

@asyncio.coroutine
def async_setup(hass, config):
    name = config[DOMAIN].get(CONF_NAME, DEFAULT_NAME)

    # Create listener
    hass.data[DOMAIN] = CommandListener(
        config[DOMAIN].get(CONF_DEVICE_INDEX, DEFAULT_DEVICE_INDEX),
        config[DOMAIN].get(CONF_SAMPLE_RATE, DEFAULT_SAMPLE_RATE),
        config[DOMAIN].get(CONF_SAMPLE_WIDTH, DEFAULT_SAMPLE_WIDTH),
        config[DOMAIN].get(CONF_CHANNELS, DEFAULT_CHANNELS),
        config[DOMAIN].get(CONF_CHUNK_SIZE, DEFAULT_CHUNK_SIZE),

        config[DOMAIN].get(CONF_VAD_MODE, DEFAULT_VAD_MODE),
        config[DOMAIN].get(CONF_MIN_SEC, DEFAULT_MIN_SEC),
        config[DOMAIN].get(CONF_SILENCE_SEC, DEFAULT_SILENCE_SEC),
        config[DOMAIN].get(CONF_TIMEOUT_SEC, DEFAULT_TIMEOUT_SEC))

    url = config[DOMAIN].get(CONF_URL, DEFAULT_URL)

    state_attrs = {
        'friendly_name': 'Command Listener',
        'icon': 'mdi:microphone-plus',
        'text': ''
    }

    @asyncio.coroutine
    def async_listen(call):
        nonlocal url

        hass.states.async_set(OBJECT_MICROPHONE, STATE_RECORDING, state_attrs)
        filename = call.data.get(ATTR_FILENAME)
        url = call.data.get(ATTR_URL, url)
        yield from hass.data[DOMAIN].async_listen(filename=filename, url=url)
        hass.states.async_set(OBJECT_MICROPHONE, STATE_IDLE, state_attrs)

        # Fire recorded event
        hass.bus.async_fire(EVENT_SPEECH_RECORDED, {
            'name': name         # name of the component
        })

    hass.services.async_register(DOMAIN, SERVICE_LISTEN, async_listen,
                                 schema=SCHEMA_SERVICE_LISTEN)

    hass.states.async_set(OBJECT_MICROPHONE, STATE_IDLE, state_attrs)

    _LOGGER.info('Started')

    return True
