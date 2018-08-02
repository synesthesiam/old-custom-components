Quickstart: Conversation
==============================

This quickstart assumes you'll be running Home Assistant and rhasspy on a Linux
desktop machine (x86_64) and using Home Assistant's built-in
[conversation](https://www.home-assistant.io/components/conversation/) component
instead of `rasaNLU`.

The following Home Assistant components from rhasspy will be used:

* `hotword_precise`
    * Can be trained offline with custom hotwords
* `stt_pocketsphinx`
    * Recommend using the non-PTM acoustic model (`cmusphinx-en-us-5.2`) for more accurate decoding
* `picotts_aplay`
    * Alternative to existing [tts.picotts](https://www.home-assistant.io/components/tts.picotts) component
    * Plays text-to-speech results directly with [aplay](https://linux.die.net/man/1/aplay)
* `wav_aplay`
    * Alternative to existing [media_player.vlc](https://www.home-assistant.io/components/media_player.vlc) component
    * Plays WAV files directly with [aplay](https://linux.die.net/man/1/aplay)

1. Debian Dependencies
---------------------------

Install these packages first from your distribution's repositories:

* General
    * `build-essential`
    * `git`
* Python
    * `python3`
    * `python3-dev`
    * `python3-pip`
    * `python3-venv`
* pocketsphinx
    * `libasound2-dev`
    * `libpulse-dev`
    * `swig`
* PyAudio
    * `portaudio19-dev`
* rhasspy
    * `libttspico-utils`
* SRILM
    * `libtcl8.6`
    
You can install them all at once with a single command:

    sudo apt-get install git build-essential \
        python3 python3-dev python3-pip python3-venv \
        libasound2-dev libpulse-dev swig \
        portaudio19-dev \
        libttspico-utils
        
2. Home Assistant
---------------------

If you don't have Home Assistant installed, you can follow one of their
[installation guides](https://www.home-assistant.io/docs/installation/) or the
instructions below (based on [Installation in Python virtual
environment](https://www.home-assistant.io/docs/installation/virtualenv/).

**NOTE**: Home Assistant requires at least Python 3.5.3

Create a virtual environment with access to system site packages:

    python3 -m venv homeassistant
    
Open the virtual environment and activate it:

    cd homeassistant
    source bin/activate
    
Install Home Assistant:

    python3 -m pip install wheel
    python3 -m pip install homeassistant
    
Run Home Assistant (wait for it to install dependencies):

    mkdir -p config
    hass -c config
    
Open a web browser and visit [http://localhost:8123](http://localhost:8123)

If all went well, you should see the Home Assistant frontend. Additionally, you
should find a `config` directory inside your `homeassistant` directory with
`configuration.yaml` and other files.

Make sure to stop Home Assistant by pressing CTRL+C in its terminal window.

3. Rhasspy Assistant
------------------------

Next, we'll download and configure rhasspy. This involves downloading the
software that rhasspy depends on (`rhasspy-tools`) as well as the Home Assistant
compnents (`rhasspy-assistant`).

Make a note of where you download these files, since you will need the enter the
full path to them during configuration.

Download rhasspy tools:

    git clone https://github.com/synesthesiam/rhasspy-tools.git
    
Download rhasspy assistant:

    git clone https://github.com/synesthesiam/rhasspy-assistant.git
    
Copy the whole `custom_components` directory in `rhasspy-assistant/config` to
your Home Assistant configuration directory (where `configuration.yaml`
resides).

Incorporate the files in `rhasspy-assistant/config/examples/conversation`
into your Home Assistant configuration. You **must** replace the following
placeholders in `configuration.yaml` and `automations.yaml`:
   
* `$RHASSPY_ASSISTANT` - replace with the full path to the `rhasspy-assistant` directory
* `$RHASSPY_TOOLS` - replace with the full path to the `rhasspy-tools` directory
     
Run Home Assistant (wait for it to install dependencies):
 
    cd homeassistant
    source bin/activate
    hass -c config
    
You can now test rhasspy with phrases like:

* "okay rhasspy" (wait for beep) "what time is it?"
* "okay rhasspy" (wait for beep) "turn on the living room lamp"
* "okay rhasspy" (wait for beep) "is the garage door open?"
* "okay rhasspy" (wait for beep) "what's the temperature like?"

Edit the `conversation` config in `configuration.yaml` to add more intents. Make
sure you copy any new phrases into your `examples.md` and re-train rhasspy. This
will ensure that the speech-to-text system can recognize the new phrases even
though a `rasaNLU` recognizer is **not** trained.
