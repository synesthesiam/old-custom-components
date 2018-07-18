Quickstart: Raspberry Pi
=============================

rhasspy will run on a Raspberry Pi 3, though some compromises have to be made
because of the limited RAM and CPU speed.

The following Home Assistant components from rhasspy will be used:
* `hotword_snowboy`
    * Low resource usage and low false positive rate
* `stt_pocketsphinx`
    * Recommend using the PTM acoustic model (`cmusphinx-en-us-ptm-5.2`) for quicker decoding
* `rasa_nlu`
    * Recommend using `en_core_web_sm` language model for `spaCy` to limit memory usage
* `picotts_aplay`
    * Alternative to existing [tts.picotts](https://www.home-assistant.io/components/tts.picotts) component
    * Plays text-to-speech results directly with [aplay](https://linux.die.net/man/1/aplay)
* `wav_aplay`
    * Alternative to existing [media_player.vlc](https://www.home-assistant.io/components/media_player.vlc) component
    * Plays WAV files directly with [aplay](https://linux.die.net/man/1/aplay)

Extend Swap Space
---------------------

Due to the limited RAM on a Raspberry Pi (1GB), the swap space must be extended
for the installation of `spaCy` and `rasaNLU`. Without this extension, the
installation of the Python dependencies will likely fail (i.e., pip will
suddenly die).

This is fairly simple to do in Raspbian:

1. Edit /etc/dphys-swapfile
2. Change `CONF_SWAPSIZE` to something large, like 2048
3. Reboot

Debian Dependencies
-----------------------

The following dependencies should be installed from the Raspbian repositories:

* General
    * `build-essential`
* Python
    * `python3`
    * `python3-dev`
    * `python3-pip`
    * `python3-venv`
* pocketsphinx
    * `libasound2-dev`
    * `libpulse-dev`
    * `swig`
* rasaNLU
    * `libatlas-dev`
    * `libatlas-base-dev`
* rhasspy
    * `libpicotts-utils`
    
You can install them all at once with a single command:

    sudo apt-get install build-essential \
        python3 python3-dev python3-pip python3-venv \
        libasound2-dev libpulse-dev swig \
        libatlas-dev libatlas-base-dev \
        libpicotts-utils
        
If the `libpictoos-utils` package is unavailable. You will find it and its
dependencies in in the `rhasspy-tools` repository mentioned below. Once you have
`rhasspy-tools` downloaded, you can install picotts with:

    cd rhasspy-tools/pico-tts
    sudo dpkg -i *.deb
    
2. Home Assistant
---------------------

If you don't have Home Assistant installed, you can follow one of their
[installation guides](https://www.home-assistant.io/docs/installation/) or the
instructions below (based on [Installation in Python virtual
environment](https://www.home-assistant.io/docs/installation/virtualenv/).

**NOTE**: Home Assistant requires at least Python 3.5.3

1. Create a virtual environment with access to system site packages:

    python3 -m venv homeassistant
    
2. Open the virtual environment and activate it:

    cd homeassistant
    source bin/activate
    
3. Install Home Assistant:

    python3 -m pip install wheel homeassistant
    
4. Run Home Assistant (wait for it to install dependencies):

    mkdir -p config
    hass -c config
    
5. Open a web browser and visit [http://localhost:8123](http://localhost:8123)

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

1. Download rhasspy tools:

    git clone https://github.com/synesthesiam/rhasspy-tools.git
    
2. Download rhasspy assistant:

    git clone https://github.com/synesthesiam/rhasspy-assistant.git
    
3. Copy the whole `custom_components` directory in `rhasspy-assistant/config` to
   your Home Assistant configuration directory (where `configuration.yaml`
   resides).

4. Incorporate the files in `rhasspy-assistant/config/examples/single_machine`
   into your Home Assistant configuration. You **must** replace the following
   placeholders in `configuration.yaml` and `automations.yaml`:
   
    * `$RHASSPY_ASSISTANT` - replace with the full path to the
      `rhasspy-assistant` directory
    * `$RHASSPY_TOOLS` - replace with the full path to the
      `rhasspy-tools` directory

5. Install snowboy

    cd homeassistant
    source bin/activate
    python3 -m pip install https://github.com/Kitt-AI/snowboy/archive/v1.3.0.tar.gz
     
6. Run Home Assistant (wait **a long time** for it to install dependencies):
 
    cd homeassistant
    source bin/activate
    hass -c config
     
7. Install a language model for `spaCy`

    cd homeassistant
    source bin/activate
    python3 -m spacy download en
    
You can now test rhasspy with phrases like:

* "okay rhasspy" (wait for beep) "what time is it?"
* "okay rhasspy" (wait for beep) "turn on the living room lamp"
* "okay rhasspy" (wait for beep) "is the garage door open?"
* "okay rhasspy" (wait for beep) "what's the temperature like?"
