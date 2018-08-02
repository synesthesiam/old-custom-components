Quickstart: Client/Server
================================

This quickstart assumes you'll be running Home Assistant and rhasspy across two
machines: one that will record, and one that will do speech/intent recognition.

The following Home Assistant components from rhasspy will be used:

* `hotword_precise`
    * Can be trained offline with custom hotwords
* `command_listener`
    * Records locally with PyAudio and the POSTs WAV data to a URL
* `stt_pocketsphinx`
    * Recommend using the non-PTM acoustic model (`cmusphinx-en-us-5.2`) for more accurate decoding
    * Accepts WAV data from a URL (`command_listener`)
* `rasa_nlu`
    * Recommend using `en_core_web_md` language model for `spaCy` to increase vocabulary
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
* rasaNLU
    * `libatlas-dev`
    * `libatlas-base-dev`
* rhasspy
    * `libttspico-utils`
    * `sox`
    
You can install them all at once with a single command:

    sudo apt-get install build-essential \
        python3 python3-dev python3-pip python3-venv \
        libasound2-dev libpulse-dev swig \
        portaudio19-dev \
        libatlas-dev libatlas-base-dev \
        libttspico-utils sox
        
2. Home Assistant
---------------------

If you don't have Home Assistant installed on your client **and** server, you
can follow one of their [installation
guides](https://www.home-assistant.io/docs/installation/) or the instructions
below (based on [Installation in Python virtual
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
-------------------------

Next, we'll download and configure rhasspy. This involves downloading the
software that rhasspy depends on (`rhasspy-tools`) as well as the Home Assistant
compnents (`rhasspy-assistant`).

Make a note of where you download these files, since you will need the enter the
full path to them during configuration.

Download rhasspy tools:

    git clone https://github.com/synesthesiam/rhasspy-tools.git
    
Download rhasspy assistant:

    git clone https://github.com/synesthesiam/rhasspy-assistant.git
    

### Client Configuration

On the client, copy the whole `custom_components` directory in `rhasspy-assistant/config` to
your Home Assistant configuration directory (where `configuration.yaml`
resides).

Incorporate the files in
`rhasspy-assistant/config/examples/client_server/client` into your Home
Assistant configuration. You **must** replace the following placeholders in
`configuration.yaml` and `automations.yaml`:
   
* `$SERVER_URL` - replace with the host name of the server where Home Assistant is running (where speech/intent recognition will happen)
* `$RHASSPY_ASSISTANT` - replace with the full path to the `rhasspy-assistant` directory
* `$RHASSPY_TOOLS` - replace with the full path to the `rhasspy-tools` directory
     
Run Home Assistant (wait for it to install dependencies):
 
    cd homeassistant
    source bin/activate
    hass -c config
     
### Server Configuration

On the server, copy the whole `custom_components` directory in
`rhasspy-assistant/config` to your Home Assistant configuration directory (where
`configuration.yaml` resides).

Incorporate the files in
`rhasspy-assistant/config/examples/client_server/server` into your Home
Assistant configuration. You **must** replace the following placeholders in
`configuration.yaml` and `automations.yaml`:
   
* `$RHASSPY_ASSISTANT` - replace with the full path to the `rhasspy-assistant` directory
* `$RHASSPY_TOOLS` - replace with the full path to the `rhasspy-tools` directory
     
Run Home Assistant (wait for it to install dependencies):
 
    cd homeassistant
    source bin/activate
    hass -c config
     
Install a language model for `spaCy`:

    cd homeassistant
    source bin/activate
    python3 -m spacy download en
    
You can now test rhasspy with phrases like:

* "okay rhasspy" (wait for beep) "what time is it?"
* "okay rhasspy" (wait for beep) "turn on the living room lamp"
* "okay rhasspy" (wait for beep) "is the garage door open?"
* "okay rhasspy" (wait for beep) "what's the temperature like?"
