"""
Provide functionality to transform speech into text using pocketsphinx.
"""
import logging
import os
import math
import asyncio
import threading
import wave
import shutil
import tempfile
import subprocess
import io

import voluptuous as vol

from homeassistant.const import CONF_NAME, EVENT_HOMEASSISTANT_STOP
from homeassistant.helpers import intent, config_validation as cv
from homeassistant.components.http import HomeAssistantView

_LOGGER = logging.getLogger(__name__)

REQUIREMENTS = ['pocketsphinx==0.1.15', 'webrtcvad==2.0.10', 'PyAudio>=0.2.8']
DEPENDENCIES = ['http']

DOMAIN = 'stt_pocketsphinx'
STT_API_ENDPOINT = '/api/%s' % DOMAIN

# ------
# Config
# ------

CONF_ACOUSTIC_MODEL = 'acoustic_model'
CONF_LANGUAGE_MODEL = 'language_model'
CONF_DICTIONARY = 'dictionary'

CONF_AUDIO_DEVICE = 'audio_device'
CONF_SAMPLE_RATE = 'sample_rate'
CONF_BUFFER_SIZE = 'buffer_size'

CONF_VAD_MODE = 'vad_mode'
CONF_MIN_SEC = 'min_sec'
CONF_SILENCE_SEC = 'silence_sec'
CONF_TIMEOUT_SEC = 'timeout_sec'

DEFAULT_NAME = 'stt_pocketsphinx'
DEFAULT_ACOUSTIC_MODEL = '/usr/share/pocketsphinx/model/en-us/en-us/'
DEFAULT_LANGUAGE_MODEL = '/usr/share/pocketsphinx/model/en-us/en-us.lm.bin'
DEFAULT_DICTIONARY = '/usr/share/pocketsphinx/model/en-us/cmudict-en-us.dict'

DEFAULT_AUDIO_DEVICE = None
DEFAULT_SAMPLE_RATE = 16000  # 16Khz
DEFAULT_BUFFER_SIZE = 480    # 30 ms (webrtcvad only supports 10,20,30 ms)

DEFAULT_VAD_MODE = 0         # 0-3 (agressiveness)
DEFAULT_MIN_SEC = 2.0        # min seconds that command must last
DEFAULT_SILENCE_SEC = 0.5    # min seconds of silence after command
DEFAULT_TIMEOUT_SEC = 30.0   # max seconds that command can last

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_NAME, DEFAULT_NAME): cv.string,

        vol.Optional(CONF_ACOUSTIC_MODEL, DEFAULT_ACOUSTIC_MODEL): cv.string,
        vol.Optional(CONF_LANGUAGE_MODEL, DEFAULT_LANGUAGE_MODEL): cv.string,
        vol.Optional(CONF_DICTIONARY, DEFAULT_DICTIONARY): cv.string,

        vol.Optional(CONF_AUDIO_DEVICE, DEFAULT_AUDIO_DEVICE): int,
        vol.Optional(CONF_SAMPLE_RATE, DEFAULT_SAMPLE_RATE): int,
        vol.Optional(CONF_BUFFER_SIZE, DEFAULT_BUFFER_SIZE): int,

        vol.Optional(CONF_VAD_MODE, DEFAULT_VAD_MODE): int,
        vol.Optional(CONF_MIN_SEC, DEFAULT_MIN_SEC): float,
        vol.Optional(CONF_SILENCE_SEC, DEFAULT_SILENCE_SEC): float,
        vol.Optional(CONF_TIMEOUT_SEC, DEFAULT_TIMEOUT_SEC): float
    })
}, extra=vol.ALLOW_EXTRA)

# --------
# Services
# --------

SERVICE_LISTEN = 'listen'
SERVICE_DECODE = 'decode_wav'

ATTR_FILENAME = 'filename'
ATTR_DATA = 'data'

SCHEMA_SERVICE_DECODE = vol.Schema({
    vol.Optional(ATTR_FILENAME): cv.string,
    vol.Optional(ATTR_DATA): list
})

OBJECT_POCKETSPHINX = '%s.pocketsphinx' % DOMAIN
STATE_IDLE = 'idle'
STATE_LISTENING = 'listening'
STATE_DECODING = 'decoding'

EVENT_SPEECH_RECORDED = 'speech_recorded'
EVENT_SPEECH_TO_TEXT = 'speech_to_text'

# -----------------------------------------------------------------------------
@asyncio.coroutine
def async_setup(hass, config):
    name = config[DOMAIN].get(CONF_NAME, DEFAULT_NAME)
    acoustic_model = os.path.expanduser(config[DOMAIN].get(CONF_ACOUSTIC_MODEL, DEFAULT_ACOUSTIC_MODEL))
    language_model = os.path.expanduser(config[DOMAIN].get(CONF_LANGUAGE_MODEL, DEFAULT_LANGUAGE_MODEL))
    dictionary = os.path.expanduser(config[DOMAIN].get(CONF_DICTIONARY, DEFAULT_DICTIONARY))

    audio_device_index = config[DOMAIN].get(CONF_AUDIO_DEVICE, DEFAULT_AUDIO_DEVICE)
    if (audio_device_index is not None) and  (audio_device_index < 0):
        audio_device_index = None  # default device

    sample_width = 2  # 16-bit
    channels = 1      # mono
    sample_rate = config[DOMAIN].get(CONF_SAMPLE_RATE, DEFAULT_SAMPLE_RATE)
    buffer_size = config[DOMAIN].get(CONF_BUFFER_SIZE, DEFAULT_BUFFER_SIZE)

    # Set up voice activity detection (VAD)
    import webrtcvad
    vad_mode = config[DOMAIN].get(CONF_VAD_MODE, DEFAULT_VAD_MODE)
    assert 0 <= vad_mode <= 3, 'VAD mode must be in [0-3]'
    vad = webrtcvad.Vad()
    vad.set_mode(vad_mode)  # agressiveness (0-3)

    # Controls how phrase is recorded
    min_sec = config[DOMAIN].get(CONF_MIN_SEC, DEFAULT_MIN_SEC)
    silence_sec = config[DOMAIN].get(CONF_SILENCE_SEC, DEFAULT_SILENCE_SEC)
    timeout_sec = config[DOMAIN].get(CONF_TIMEOUT_SEC, DEFAULT_TIMEOUT_SEC)
    seconds_per_buffer = buffer_size / sample_rate

    # Create speech-to-text decoder
    from pocketsphinx import Pocketsphinx, Ad
    decoder = Pocketsphinx(
        hmm=acoustic_model,
        lm=language_model,
        dic=dictionary)

    import pyaudio
    data_format = pyaudio.get_format_from_width(sample_width)

    # Events for asynchronous recording/decoding
    recorded_event = threading.Event()
    decoded_event = threading.Event()
    decoded_phrase = None
    terminated = False

    # -------------------------------------------------------------------------

    state_attrs = {
        'friendly_name': 'Speech to Text',
        'icon': 'mdi:comment-text',
        'text': ''
    }

    @asyncio.coroutine
    def async_listen(call):
        nonlocal decoded_phrase, terminated
        decoded_phrase = None
        terminated = False

        hass.states.async_set(OBJECT_POCKETSPHINX, STATE_LISTENING, state_attrs)

        # Recording state
        max_buffers = int(math.ceil(timeout_sec / seconds_per_buffer))
        silence_buffers = int(math.ceil(silence_sec / seconds_per_buffer))
        min_phrase_buffers = int(math.ceil(min_sec / seconds_per_buffer))
        in_phrase = False
        after_phrase = False
        finished = False

        recorded_data = bytearray()

        # PyAudio callback for each buffer from audio device
        def stream_callback(buf, frame_count, time_info, status):
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

            # Detect speech in buffer
            is_speech = vad.is_speech(buf, sample_rate)
            if is_speech and not in_phrase:
                # Start of phrase
                in_phrase = True
                after_phrase = False
                recorded_data += buf
                min_phrase_buffers = int(math.ceil(min_sec / seconds_per_buffer))
            elif in_phrase and (min_phrase_buffers > 0):
                # In phrase, before minimum seconds
                recorded_data += buf
                min_phrase_buffers -= 1
            elif in_phrase and is_speech:
                # In phrase, after minimum seconds
                recorded_data += buf
            elif not is_speech:
                # Outside of speech
                if after_phrase and (silence_buffers > 0):
                    # After phrase, before stop
                    recorded_data += buf
                    silence_buffers -= 1
                elif after_phrase and (silence_buffers <= 0):
                    # Phrase complete
                    recorded_data += buf
                    finished = True

                    # Reset
                    in_phrase = False
                    after_phrase = False
                elif in_phrase and (min_phrase_buffers <= 0):
                    # Transition to after phrase
                    after_phrase = True
                    silence_buffers = int(math.ceil(silence_sec / seconds_per_buffer))

            if finished:
                recorded_event.set()

            return (buf, pyaudio.paContinue)

        # Open microphone device
        audio = pyaudio.PyAudio()
        mic = audio.open(format=data_format,
                         channels=channels,
                         rate=sample_rate,
                         input_device_index=audio_device_index,
                         input=True,
                         stream_callback=stream_callback,
                         frames_per_buffer=buffer_size)

        loop = asyncio.get_event_loop()

        # Wait for recorded to complete
        recorded_event.clear()
        mic.start_stream()
        yield from loop.run_in_executor(None, recorded_event.wait)

        # Stop audio
        mic.stop_stream()
        mic.close()
        audio.terminate()

        if not terminated:
            # Fire recorded event
            hass.bus.async_fire(EVENT_SPEECH_RECORDED, {
                'name': name,  # name of the component
                'size': len(recorded_data)  # bytes of recorded audio data
            })

            hass.states.async_set(OBJECT_POCKETSPHINX, STATE_DECODING, state_attrs)

            def decode():
                nonlocal decoded_phrase
                with decoder.start_utterance():
                    decoder.process_raw(recorded_data, False, True)  # full utterance
                    hyp = decoder.hyp()
                    if hyp:
                        with decoder.end_utterance():
                            decoded_phrase = hyp.hypstr

                decoded_event.set()

            # Decode in separate thread
            decoded_event.clear()
            thread = threading.Thread(target=decode, daemon=True)
            thread.start()
            yield from loop.run_in_executor(None, decoded_event.wait)

            if not terminated:
                thread.join()
                state_attrs['text'] = decoded_phrase
                hass.states.async_set(OBJECT_POCKETSPHINX, STATE_IDLE, state_attrs)

                # Fire decoded event
                hass.bus.async_fire(EVENT_SPEECH_TO_TEXT, {
                    'name': name,  # name of the component
                    'text': decoded_phrase
                })

    # -------------------------------------------------------------------------

    @asyncio.coroutine
    def async_decode(call):
        nonlocal decoded_phrase, terminated
        decoded_phrase = None
        terminated = False

        if ATTR_FILENAME in call.data:
            # Use WAV file
            filename = call.data[ATTR_FILENAME]
            with wave.open(filename, mode='rb') as wav_file:
                data = wav_file.readframes(wav_file.getnframes())
        else:
            # Use data directly from JSON
            filename = None
            data = bytearray(call.data[ATTR_DATA])

        hass.states.async_set(OBJECT_POCKETSPHINX, STATE_DECODING, state_attrs)

        def decode():
            nonlocal decoded_phrase, data, filename

            # Check if WAV is in the correct format.
            # Convert with sox if not.
            with io.BytesIO(data) as wav_data:
                with wave.open(wav_data, mode='rb') as wav_file:
                    rate, width, channels = wav_file.getframerate(), wav_file.getsampwidth(), wav_file.getnchannels()
                    _LOGGER.debug('rate=%s, width=%s, channels=%s.' % (rate, width, channels))

                    if (rate != 16000) or (width != 2) or (channels != 1):
                        # Convert to 16-bit 16Khz mono (required by pocketsphinx acoustic models)
                        _LOGGER.debug('Need to convert to 16-bit 16Khz mono.')
                        if shutil.which('sox') is None:
                            _LOGGER.error("'sox' command not found. Cannot convert WAV file to appropriate format. Expect poor performance.")
                        else:
                            temp_input_file = None
                            if filename is None:
                                # Need to write original WAV data out to a file for sox
                                temp_input_file = tempfile.NamedTemporaryFile(suffix='.wav', mode='wb+')
                                temp_input_file.write(data)
                                temp_input_file.seek(0)
                                filename = temp_input_file.name

                            # sox <IN> -r 16000 -e signed-integer -b 16 -c 1 <OUT>
                            with tempfile.NamedTemporaryFile(suffix='.wav', mode='wb+') as out_wav_file:
                                subprocess.check_call(['sox',
                                                       filename,
                                                       '-r', '16000',
                                                       '-e', 'signed-integer',
                                                       '-b', '16',
                                                       '-c', '1',
                                                       out_wav_file.name])

                                out_wav_file.seek(0)

                                # Use converted data
                                with wave.open(out_wav_file, 'rb') as wav_file:
                                    data = wav_file.readframes(wav_file.getnframes())

                            if temp_input_file is not None:
                                # Clean up temporary file
                                del temp_input_file

            # Process WAV data as a complete utterance (best performance)
            with decoder.start_utterance():
                decoder.process_raw(data, False, True)  # full utterance
                if decoder.hyp():
                    with decoder.end_utterance():
                        decoded_phrase = decoder.hyp().hypstr

            decoded_event.set()

        loop = asyncio.get_event_loop()

        # Decode in separate thread
        decoded_event.clear()
        thread = threading.Thread(target=decode, daemon=True)
        thread.start()
        yield from loop.run_in_executor(None, decoded_event.wait)

        if not terminated:
            thread.join()
            state_attrs['text'] = decoded_phrase
            hass.states.async_set(OBJECT_POCKETSPHINX, STATE_IDLE, state_attrs)

            # Fire decoded event
            hass.bus.async_fire(EVENT_SPEECH_TO_TEXT, {
                'name': name,  # name of the component
                'text': decoded_phrase
            })

    # -------------------------------------------------------------------------

    hass.http.register_view(ExternalSpeechView)

    # Service to record commands
    hass.services.async_register(DOMAIN, SERVICE_LISTEN, async_listen)

    # Service to do speech to text
    hass.services.async_register(DOMAIN, SERVICE_DECODE, async_decode,
                                 schema=SCHEMA_SERVICE_DECODE)

    hass.states.async_set(OBJECT_POCKETSPHINX, STATE_IDLE, state_attrs)

    # Make sure everything terminates property when home assistant stops
    @asyncio.coroutine
    def async_terminate(event):
        nonlocal terminated
        terminated = True
        recorded_event.set()
        decoded_event.set()

    hass.bus.async_listen(EVENT_HOMEASSISTANT_STOP, async_terminate)

    _LOGGER.info('Started')

    return True

# -----------------------------------------------------------------------------


class ExternalSpeechView(HomeAssistantView):
    """Handle speech to text requests."""

    url = STT_API_ENDPOINT
    name = 'api:%s' % DOMAIN

    async def post(self, request):
        """Handle speech to text."""
        hass = request.app['hass']
        data = await request.read()

        _LOGGER.debug("Received speech to text request: %s byte(s)", len(data))

        await hass.services.async_call(DOMAIN, SERVICE_DECODE,
                                       { ATTR_DATA: list(data) })

        return 'OK'
