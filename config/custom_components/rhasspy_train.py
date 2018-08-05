"""
Provides functionality for training the rhasspy voice assistant.
"""
import logging
import os
import shutil
import sys
import re
import subprocess
import tempfile
import asyncio
import threading
from collections import defaultdict

import voluptuous as vol

from homeassistant.helpers import config_validation as cv

_LOGGER = logging.getLogger(__name__)

# rasaNLU is only required if you use it instead of the conversation component.
# If you use the rasa_nlu component, then you should already have these
# requirements installed.
#REQUIREMENTS = ['rasa-nlu==0.12.3', 'spacy==2.0.11']

# Executables that are expected to be in the PATH
REQUIRED_TOOLS = ['ngram-count', 'phonetisaurus-g2p', 'ngram']

DOMAIN = 'rhasspy_train'

# ------
# Config
# ------

# Path to SRILM ngram tool (default assumes it's on the PATH)
CONF_NGRAM = 'ngram_path'

# Path to SRILM ngram-count tool (default assumes it's on the PATH)
CONF_NGRAM_COUNT = 'ngram_count_path'

# Path to phonetisaurus-g2p tool (default assumes it's on the PATH)
CONF_PHONETISAURUS = 'phonetisaurus_path'

# Path to finite state transducer trained for phonetisaurus-g2p
CONF_G2P_FST = 'phonetisaurus_fst'

# Directory where rasaNLU projects are stored
CONF_PROJECT_DIR = 'project_dir'

# Name of the generated rasaNLU project (defaults to 'rhasspy')
CONF_PROJECT_NAME = 'project_name'

# List of paths to Markdown files with training examples
CONF_EXAMPLE_FILES = 'example_files'

# Path to YAML configuration file for rasaNLU
CONF_RASA_CONFIG = 'rasa_config'

# Number of threads to use when training rasaNLU model (defaults to 4)
CONF_RASA_THREADS = 'rasa_threads'

# List of paths to Sphinx dictionary files with word pronounciations (.dict)
CONF_DICT_FILES = 'dictionary_files'

# Path to Sphinx dictionary file with generated pronounciations from phonetisaurus
CONF_DICT_GUESS = 'dictionary_guess'

# Path to write Sphinx dictionary file with all known/generated words
CONF_DICT_MIXED = 'dictionary_mixed'

# Path to large English language model (.lm)
CONF_LM_BASE = 'language_model_base'

# Path to small language model generated from training examples
CONF_LM_EXAMPLE = 'language_model_example'

# Path to combined language model (large English + small generated)
CONF_LM_MIXED = 'language_model_mixed'

# Percentage of large language model to "mix" into smaller model (defaults to 5%)
CONF_LM_LAMBDA = 'language_model_mix_percent'

# ----------------------
# Configuration defaults
# ----------------------

DEFAULT_NGRAM = 'ngram'
DEFAULT_NGRAM_COUNT = 'ngram-count'
DEFAULT_PHONETISAURUS = 'phonetisaurus-g2p'
DEFAULT_PROJECT_NAME = 'rhasspy'
DEFAULT_LM_LAMBDA = 0.05
DEFAULT_RASA_THREADS = 4

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({
        vol.Optional(CONF_NGRAM, DEFAULT_NGRAM): cv.string,
        vol.Optional(CONF_NGRAM_COUNT, DEFAULT_NGRAM_COUNT): cv.string,
        vol.Optional(CONF_PHONETISAURUS, DEFAULT_PHONETISAURUS): cv.string,

        vol.Optional(CONF_PROJECT_DIR, None): cv.string,
        vol.Optional(CONF_PROJECT_NAME, DEFAULT_PROJECT_NAME): cv.string,
        vol.Required(CONF_EXAMPLE_FILES): list,
        vol.Optional(CONF_RASA_CONFIG, None): cv.string,
        vol.Optional(CONF_RASA_THREADS, DEFAULT_RASA_THREADS): int,

        vol.Required(CONF_DICT_FILES): list,
        vol.Required(CONF_DICT_GUESS): cv.string,
        vol.Required(CONF_DICT_MIXED): cv.string,

        vol.Required(CONF_LM_BASE): cv.string,
        vol.Required(CONF_LM_EXAMPLE): cv.string,
        vol.Required(CONF_LM_MIXED): cv.string,
        vol.Optional(CONF_LM_LAMBDA, DEFAULT_LM_LAMBDA): float,

        vol.Required(CONF_G2P_FST): cv.string,
    })
}, extra=vol.ALLOW_EXTRA)

# --------
# Services
# --------

# Represents the trainer
OBJECT_TRAINER = '%s.trainer' % DOMAIN

# Not training
STATE_IDLE = 'idle'

# Training
STATE_TRAINING = 'training'

# Service to re-train rhasspy
SERVICE_TRAIN = 'train'

# Fired when training has been completed
EVENT_RHASSPY_TRAINED = 'rhasspy_trained'

@asyncio.coroutine
def async_setup(hass, config):
    # Extract config values
    ngram = os.path.expanduser(config[DOMAIN].get(CONF_NGRAM, DEFAULT_NGRAM))
    ngram_count = os.path.expanduser(config[DOMAIN].get(CONF_NGRAM_COUNT, DEFAULT_NGRAM_COUNT))
    phonetisaurus = os.path.expanduser(config[DOMAIN].get(CONF_PHONETISAURUS, DEFAULT_PHONETISAURUS))
    g2p_fst = os.path.expanduser(config[DOMAIN][CONF_G2P_FST])

    project_dir = config[DOMAIN].get(CONF_PROJECT_DIR, None)
    if project_dir is not None:
        project_dir = os.path.expanduser(project_dir)

    project_name = config[DOMAIN].get(CONF_PROJECT_NAME, DEFAULT_PROJECT_NAME)
    example_files = [os.path.expanduser(path) for path in config[DOMAIN][CONF_EXAMPLE_FILES]]

    rasa_config = config[DOMAIN].get(CONF_RASA_CONFIG, None)
    if rasa_config is not None:
        rasa_config = os.path.expanduser(rasa_config)

    rasa_threads = config[DOMAIN].get(CONF_RASA_THREADS, DEFAULT_RASA_THREADS)

    dict_files = [os.path.expanduser(path) for path in config[DOMAIN][CONF_DICT_FILES]]
    dict_guess = os.path.expanduser(config[DOMAIN][CONF_DICT_GUESS])
    dict_mixed = os.path.expanduser(config[DOMAIN][CONF_DICT_MIXED])

    lm_base = os.path.expanduser(config[DOMAIN][CONF_LM_BASE])
    lm_example = os.path.expanduser(config[DOMAIN][CONF_LM_EXAMPLE])
    lm_mixed = os.path.expanduser(config[DOMAIN][CONF_LM_MIXED])
    lm_lambda = config[DOMAIN].get(CONF_LM_LAMBDA, DEFAULT_LM_LAMBDA)

    state_attrs = {
        'friendly_name': 'Trainer',
        'icon': 'mdi:paperclip'
    }

    @asyncio.coroutine
    def async_train(call):
        trained_event = threading.Event()

        def train():
            _LOGGER.info('Starting training')
            hass.states.async_set(OBJECT_TRAINER, STATE_TRAINING, state_attrs)

            try:
                # Optionally train project for rasaNLU
                if (project_dir is not None) and (rasa_config is not None):
                    train_intent_recognizer(example_files, rasa_config,
                                            project_dir, project_name,
                                            num_threads=rasa_threads)

                # Train language model for pocketsphinx
                train_speech_recognizer(example_files,
                                        dict_files, dict_guess, dict_mixed,
                                        lm_base, lm_example, lm_mixed, lm_lambda,
                                        ngram, ngram_count, phonetisaurus, g2p_fst)

                _LOGGER.info('Finished training')
            finally:
                trained_event.set()
                hass.bus.async_fire(EVENT_RHASSPY_TRAINED)
                hass.states.async_set(OBJECT_TRAINER, STATE_IDLE, state_attrs)

        thread = threading.Thread(target=train, daemon=True)
        thread.start()

        loop = asyncio.get_event_loop()
        yield from loop.run_in_executor(None, trained_event.wait)

    hass.services.async_register(DOMAIN, SERVICE_TRAIN, async_train)

    hass.states.async_set(OBJECT_TRAINER, STATE_IDLE, state_attrs)

    _LOGGER.info('Started')

    return True

# -----------------------------------------------------------------------------

def train_intent_recognizer(example_files, rasa_config,
                            project_dir, project_name,
                            num_threads=4):
    import rasa_nlu
    from rasa_nlu.train import do_train

    # Write training examples out to single file
    with tempfile.NamedTemporaryFile(suffix='.md', mode='w+') as train_file:
        for example_path in example_files:
            if not os.path.exists(example_path):
                continue

            # Copy contents
            with open(example_path, 'r') as example_file:
                for line in example_file:
                    print(line, file=train_file)

            # Back to beginining
            train_file.seek(0)

            # Run the actual training
            do_train(cfg=rasa_nlu.config.load(rasa_config),
                     data=train_file.name,
                     path=project_dir,
                     project=project_name,
                     num_threads=num_threads)

# -----------------------------------------------------------------------------

def train_speech_recognizer(example_files,
                            dict_files, dict_guess, dict_mixed,
                            lm_base, lm_example, lm_mixed, lm_lambda,
                            ngram, ngram_count, phonetisaurus, g2p_fst):
    # Load examples
    intent_examples = load_training_phrases(example_files)

    # Write clean sentences to a file
    with tempfile.NamedTemporaryFile(suffix='.vocab', mode='w+') as vocab_file:
        with tempfile.NamedTemporaryFile(suffix='.txt', mode='w+') as sentences_file:
            sentences = [example['clean']
                        for k, v in intent_examples.items()
                        for example in v]

            for sentence in sentences:
                print(sentence, file=sentences_file)

            # Generate language model and vocabulary
            sentences_file.seek(0)
            lm_command = [ngram_count,
                          '-interpolate',
                          '-text', sentences_file.name,
                          '-lm', lm_example,
                          '-write-vocab', vocab_file.name]

            _LOGGER.debug(lm_command)
            subprocess.check_call(lm_command)

        # Read dictionaries
        word_dict = defaultdict(set)
        for dict_path in dict_files:
            if not os.path.exists(dict_path):
                continue

            read_dict(dict_path, word_dict)

        # Check vocabulary
        vocab_words = []
        vocab_file.seek(0)
        for line in vocab_file:
            line = line.strip()
            if (len(line) == 0) or line.startswith('-') or line.startswith('<'):
                continue  # skip blank lines and silence phones

            vocab_words.append(line)

        unknown_words = set()
        for word in vocab_words:
            if not word in word_dict:
                unknown_words.add(word)

        if len(unknown_words) > 0:
            _LOGGER.warn('Unknown words: %s' % unknown_words)
            ws_pattern = re.compile(r'\s+')

            # Write words
            with tempfile.NamedTemporaryFile(mode='w', suffix='.g2p') as word_file:
                for word in unknown_words:
                    # MUST use upper-case for phonetisaurus
                    print(word.upper(), file=word_file)

                with tempfile.NamedTemporaryFile(mode='r+', suffix='.txt') as pronounce_file:
                    word_file.seek(0)
                    g2p_command = [phonetisaurus,
                                   '--model=' + g2p_fst,
                                   '--input=' + word_file.name,
                                   '--isfile',
                                   '--nbest=1',
                                   '--words']

                    _LOGGER.debug(g2p_command)
                    subprocess.check_call(g2p_command, stdout=pronounce_file)

                    # Add to unknown dictionary
                    with open(dict_guess, 'w') as guess_file:
                        # Transform to dict format
                        # Phonetisaurus: WORD SCORE <s> PHONEMES </s>
                        # Dict: WORD PHONEMES
                        pronounce_file.seek(0)
                        for line in pronounce_file:
                            parts = ws_pattern.split(line)
                            word = parts[0].lower()
                            phonemes = parts[3:-2]
                            print(' '.join([word] + phonemes), file=guess_file)

                            # Add to mixed dictionary
                            word_dict[word].add(' '.join(phonemes))

        # Write merged dictionary
        with open(dict_mixed, 'w') as mixed_dict:
            for word, pronounces in sorted(word_dict.items()):
                for i, pronounce in enumerate(pronounces):
                    if i > 0:
                        w = '{0}({1})'.format(word, i + 1)
                    else:
                        w = word
                    print(w.lower(), pronounce.upper(), file=mixed_dict)

        # Mix with base language model
        mix_command = [ngram,
                       '-lm', lm_base,
                       '-lambda', str(lm_lambda),
                       '-mix-lm', lm_example,
                       '-write-lm', lm_mixed]

        _LOGGER.debug(mix_command)
        subprocess.check_call(mix_command)

# -----------------------------------------------------------------------------

def load_training_phrases(data_paths):
    intent_phrases = defaultdict(list)

    for data_path in data_paths:
        if not os.path.exists(data_path):
            continue

        with open(data_path, 'r') as data_file:
            intent_name = None
            intent_regex = re.compile(r'^##\s+intent:(.+)$')
            for line in data_file:
                line = line.strip()
                if line.startswith('##'):
                    match = intent_regex.search(line)
                    if match is not None:
                        # intent:<name>
                        intent_name = match.group(1)
                    else:
                        # Not an intent
                        intent_name = None
                elif intent_name is not None and line.startswith('-'):
                    # Example
                    raw_phrase = line[1:].strip()
                    phrase_text, entities = extract_entities(raw_phrase)
                    clean_text = sanitize_phrase(phrase_text)
                    intent_phrases[intent_name].append({
                        'raw': raw_phrase,
                        'text': phrase_text,
                        'clean': clean_text,
                        'entities': entities
                    })

    return intent_phrases

def sanitize_phrase(phrase):
    """
    Prepares a phrase to be used by the speech recognition system.

    Arguments:
    phrase -- text string

    Returns:
    text string with unusable characters/words removed

    Does the following:
    0) Lower-cases
    1) Removes apostrophes, commas, colons
    2) Replaces ampersands with 'and'
    3) Replaces digits with number words (2 -> two)
    4) Replaces ii and iii Roman numerals with two and three
    5) Dashes (-) are replaced with spaces
    6) Anything that's not whitespace, an underscore, or alphanumeric is replaced with whitespace.
    """
    phrase = phrase.lower()
    phrase = phrase.replace("'s", 's')  # remove apostrophes
    phrase = phrase.replace(',', '')  # remove commas
    phrase = phrase.replace(':', '')  # remove colons
    phrase = phrase.replace('&', 'and')  # replace &

    # Replace numbers with words
    phrase = re.sub(r'\b([0-9]+)\b', lambda m: num2words(int(m.group(1))), phrase)

    # Replace Roman numerals with words
    phrase = re.sub(r'\biii\b', 'three', phrase)
    phrase = re.sub(r'\bii\b', 'two', phrase)

    # Replace dashes with spaces
    phrase = phrase.replace('-', ' ')

    # Replace everything that's not:
    # 1) alpha-numeric
    # 2) an underscore
    # 3) whitespace
    return re.sub(r'[^a-z0-9_\s]', ' ', phrase)

# -----------------------------------------------------------------------------

def extract_entities(phrase):
    """
    Extracts embedded entity markings from a phrase.
    Returns the phrase with entities removed and a list of entities.

    The format [some text](entity name) is used to mark entities in a training phrase.
    """
    start = 0  # start of current value
    offset = 0  # number of chars removed from original phrase
    in_value = False  # True when inside [...]
    between_value_entity = False  # True at [...]^(...)
    in_entity = False  # True when inside (...)
    value = ''  # current value inside [...]
    entity = ''  # current entity inside (...)

    new_phrase = ""  # phrase with DSL stripped
    entities = []  # list of parsed entities

    for i, c in enumerate(phrase):
        if in_value and (c == ']'):
            # Value end
            offset += 1
            in_value = False
            between_value_entity = True
        elif in_value:
            # Inside value
            value += c
            new_phrase += c
        elif in_entity and (c == ')'):
            # Entity end
            offset += 1
            in_entity = False
            entities.append({
                'start': start,
                'end': (start + len(value)),
                'value': value,
                'entity': entity
            })
        elif in_entity:
            # Inside entity
            offset += 1
            entity += c
        elif between_value_entity and (c == '('):
            # Between value/entity
            offset += 1
            between_value_entity = False
            in_entity = True
        elif between_value_entity and (c != '('):
            # Not a [...](...) pattern, skip
            between_value_entity = False
            new_phrase += c
        elif c == '[':
            # Value start
            start = i - offset
            offset += 1
            in_value = True
            value = ''
            entity = ''
        else:
            # Regular character
            new_phrase += c
            start += 1

    return new_phrase, entities

# -----------------------------------------------------------------------------

def read_dict(dict_path, word_dict):
    with open(dict_path, 'r') as dict_file:
        for line in dict_file:
            line = line.strip()
            if len(line) == 0:
                continue

            word, pronounce = re.split('\s+', line, maxsplit=1)
            idx = word.find('(')
            if idx > 0:
                word = word[:idx]

            word_dict[word].add(pronounce.strip())
