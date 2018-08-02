Detailed Raspberry Pi Installation
=========================================

This tutorial details the installation and use of Rhasspy on a Raspberry Pi.
Experience with SSH and Linux terminal commands is assumed.

Hardware
----------

The hardware required for this tutorial:

* Raspberry Pi 3
* 16 GB microSD card
* Sony PS3 Eye Camera/Microphone (USB)
* Speaker/headphones connected via 3.5mm audio jack

Installing Raspbian
-----------------------

The first step is to install the Raspbian operating system on your Raspberry Pi.
We'll be using a headless (console-based) version to conserve RAM and CPU
resources.

On your PC or laptop, download Raspbian Stretch Lite from [the official
website](https://www.raspberrypi.org/downloads/raspbian). At the time of this
writing, the latest version is 2018-06-27.

Follow the [installation
instructions](https://www.raspberrypi.org/documentation/installation/installing-images/README.md)
to flash your microSD card with `2018-06-27-raspbian-stretch-lite.zip`.

### Enabling SSH on First Boot

If you don't have a screen or keyboard for the Pi, you'll need to enable SSH so
you can remote in without running `raspi-config`. If you do have a screen and
keyboard, skip this part. After flashing, open the `boot` partition on the
microSD card and create a file called `ssh` (empty). This will enable the SSH
service when the Pi first boots.

### Enabling WiFi on First Boot

If your Pi will be connecting to the Internet over WiFi, you should create a
file in the `boot` partition of the microSD card called `wpa_supplicant.conf`
and add the following contents with a text editor:

    ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
    
    network={
        ssid="WiFi_SSID"
        psk="WiFi_Password"
    }
    
Make sure to change `WiFi_SSID` and `WiFi_Password` appropriately.

### Starting up the Pi

Put the microSD card into your Pi and plug it in. If you don't have a screen or
keyboard, you'll need to check your router to see what the Pi's IP address is
after it boots. Once you get that, run `ssh pi@XXX.XXX.XXX.XXX` in a terminal on
your PC to connect to the Pi (`XXX.XXX.XXX.XXX` is the IP address if the Pi,
probably something like `192.168.1.101`).

The default password is `raspberry`. You can change it at any point by running
`passwd` on the Pi (or over ssh).

Installing Software
-----------------------

If you've successfully connected your Pi to the Internet, we can start
installing software.

### Installing System Packages

First, you should update your system package indexes:

    sudo apt-get update
    
Next, install the required system packages:

    sudo apt-get install git build-essential \
        python3 python3-dev python3-pip python3-venv \
        libasound2-dev libpulse-dev swig \
        portaudio19-dev \
        libttspico-utils \
        libtcl8.6 \
        libatlas-dev libatlas-base-dev
        
### Installing Home Assistant

The next step will be to install Home Assistant and get it configured. Make sure
you're in your home directory:

    cd /home/pi
    
We'll start by created a self-contained Python virtual environment so that Home
Assistant's libraries won't interfere with anything else on the system:

    python3 -m venv homeassistant
    
To install Python libraries inside the virtual environment, we'll need to
"activate" it:

    cd homeassistant
    source bin/activate
    
You should see the command prompt change to something like `(homeassistant)`.
Now, we can install Home Assistant itself:

    python3 -m pip install wheel
    python3 -m pip install homeassistant
    
If all is well, we should be able to start Home Assistant and let it finish the
installation (this may take several minutes to complete):

    mkdir -p config
    hass -c config

Once Home Assistant finishes installing all of its dependencies (~5 minutes),
you should be able to see it on a web browser at
[http://XXX.XXX.XXX.XXX:8123](http://XXX.XXX.XXX.XXX:8123) where
`XXX.XXX.XXX.XXX` is the IP address of your Pi. You can find this out by running
`ifconfig` and looking for something like `192.168.1.101` in the output.

If you see the Home Assistant front end, congratulations! It's finally time to
install Rhasspy.

Installing Rhasspy
----------------------

The first step of installing Rhasspy is pulling the software down from GitHub.
Make sure you're in your home directory first:

    cd /home/pi
    
Now clone both the assistant and tools repositories:

    git clone https://github.com/synesthesiam/rhasspy-tools.git
    git clone https://github.com/synesthesiam/rhasspy-assistant.git
    
The `rhasspy-assistant` repository contains code and configuration files for
Home Assistant. The `rhasspy-tools` repository contains tools for re-training
Rhasspy and a web interface for testing.

Copy the custom components and configuration files for Rhasspy to your Home
Assistant directory:

    cp -R rhasspy-assistant/config/custom_components homeassistant/config/
    cp rhasspy-assistant/config/examples/raspberry_pi/*.yaml homeassistant/config/
    
Next, replace the placeholders in the configuration files with full paths to the
repositories you should downloaded:

    sed -ri 's|\$RHASSPY_ASSISTANT|/home/pi/rhasspy-assistant|g' homeassistant/config/*.yaml
    sed -ri 's|\$RHASSPY_TOOLS|/home/pi/rhasspy-tools|g' homeassistant/config/*.yaml
    
For the curious, the `sed` commands above do an in-place find and replace
(overwriting the original files).

Since we'll be using `snowboy` for hotword detection, we need to install that
next. This command assumes that your Home Assistant virtual environment is still
active (i.e., your prompt still reads `(homeassistant)`):

    python3 -m pip install https://github.com/Kitt-AI/snowboy/archive/v1.3.0.tar.gz
    
Rhasspy is now installed! Let's test it out.
    
Testing the Microphone
---------------------------

Plug in PS3 Eye camera/microphone if you haven't already, and run the following
command to ensure that ALSA has detected it:

    arecord -L
    
Here's what I got when I ran that command:

    null
        Discard all samples (playback) or generate zero samples (capture)
    default:CARD=CameraB409241
        USB Camera-B4.09.24.1, USB Audio
        Default Audio Device
    sysdefault:CARD=CameraB409241
        USB Camera-B4.09.24.1, USB Audio
        Default Audio Device
    front:CARD=CameraB409241,DEV=0
        USB Camera-B4.09.24.1, USB Audio
        Front speakers
    surround21:CARD=CameraB409241,DEV=0
        USB Camera-B4.09.24.1, USB Audio
        2.1 Surround output to Front and Subwoofer speakers
    surround40:CARD=CameraB409241,DEV=0
        USB Camera-B4.09.24.1, USB Audio
        4.0 Surround output to Front and Rear speakers
    surround41:CARD=CameraB409241,DEV=0
        USB Camera-B4.09.24.1, USB Audio
        4.1 Surround output to Front, Rear and Subwoofer speakers
    surround50:CARD=CameraB409241,DEV=0
        USB Camera-B4.09.24.1, USB Audio
        5.0 Surround output to Front, Center and Rear speakers
    surround51:CARD=CameraB409241,DEV=0
        USB Camera-B4.09.24.1, USB Audio
        5.1 Surround output to Front, Center, Rear and Subwoofer speakers
    surround71:CARD=CameraB409241,DEV=0
        USB Camera-B4.09.24.1, USB Audio
        7.1 Surround output to Front, Center, Side, Rear and Woofer speakers
    iec958:CARD=CameraB409241,DEV=0
        USB Camera-B4.09.24.1, USB Audio
        IEC958 (S/PDIF) Digital Audio Output
    dmix:CARD=CameraB409241,DEV=0
        USB Camera-B4.09.24.1, USB Audio
        Direct sample mixing device
    dsnoop:CARD=CameraB409241,DEV=0
        USB Camera-B4.09.24.1, USB Audio
        Direct sample snooping device
    hw:CARD=CameraB409241,DEV=0
        USB Camera-B4.09.24.1, USB Audio
        Direct hardware device without any conversions
    plughw:CARD=CameraB409241,DEV=0
        USB Camera-B4.09.24.1, USB Audio
        Hardware device with all software conversions
        
See the lines at the end with `USB Camera`? That's the PS3 Eye. I don't know
much about ALSA, but the `plughw` device seems to be the correct one. I copied
and pasted the name of that device for this next command:

    arecord -D plughw:CARD=CameraB409241,DEV=0 -r 16000 -c 1 -f S16_LE > test.wav
    
This records a WAV file to `test.wav` in your current directory from the PS3
Eye. Go ahead and say something, then press `CTRL+C` to stop recording. You can
play the WAV file with this command:

    aplay test.wav
    
Hopefully, you heard whatever you said before. If not, it could be that your Pi
is pushing audio out of the HDMI instead of the 3.5mm jack (if you have a screen
plugged in). In that case, running this sometimes helps:

    sudo amixer cset numid=1
    
I guess 0 is for auto, 1 for 3.5mm, and 2 is for HDMI.

Running Rhasspy
------------------

It's time to try and run Rhasspy for the first time. Make sure you're in your
Home Assistant directory and that your virtual environment is still activated:

    cd /home/pi/homeassistant/
    hass -c config

Wait a few minutes and watch the terminal output for any errors. Home Assistant
will attempt to install all of Rhasspy's dependencies before starting up. If you
do see errors, please report them to me [on
GitHub](https://github.com/synesthesiam/rhasspy-assistant.git).

Once Home Assistant finally starts, go to your web browser and reload the Home
Assistant page for the Pi. You will hopefully see something like this:

<p align="center">
  <img src="img/screenshot_raspberry-pi.png" alt="Rhasspy screenshot" width="600px" />
</p>

Try saying "okay rhasspy". You should hear a beep and the "Speech to text"
component should switch from "idle" to "listening". Now say a command, like
"what time is it?". After a moment, there should be another beep, and what you
Rhassy thinks you said will appear beside "Last Text". Additionally, Home
Assistant should respond with the current time.

Here are some other commands you can try:

    "okay rhasspy"
    "turn on the garage light"

    "okay rhasspy"
    "is the garage door open?"
    
Customizing Rhasspy
-----------------------

To make Rhasspy's speech recognizer understand more sentences, you need to
modify `examples.md` in `/home/pi/rhasspy-assistant/data`.

For example, let's say you want to have Rhasspy understand a command to "switch
on all the lights" or "switch off all the lights". Unfortunately, we can't using
"turn" instead of "switch" because that interferes with Home Assistant's
built-in `conversation` component.

Add the following lines at the end of `examples.md`:

    ## intent:SwitchOffAllLights
    - switch off all the lights
    - switch off all lights

    ## intent:SwitchOnAllLights
    - switch on all the lights
    - switch on all lights

Go to the services tab in Home Assistant and run the `rhasspy_train.train`
service with no JSON input. Watch your log carefully for errors (and report them
please!). Once training is finished, Rhasspy will be ready to listen for new
commands. However, Home Assistant won't know what to do with them.

Edit `/home/pi/homeassistant/config/configuration.yaml` and add the following
lines to the `intents` sub-section of `conversation`:

    SwitchOffAllLights:
      - switch off all the lights
      - switch off all lights
    SwitchOnAllLights:
      - switch on all the lights
      - switch on all lights
      
This is essentially a repeat of what was in `examples.md` with slightly
different formatting. Using the `rasa_nlu` component from the other quickstarts
makes it so you don't need to duplicate effort here, but it's harder to get
installed.
  
Lastly, add the following lines to the `intent_script` block:

    TurnOffAllLights:
    action:
      service: switch.turn_off
      entity_id: switch.living_room_lamp, switch.garage_light
    TurnOnAllLights:
      action:
        service: switch.turn_on
        entity_id: switch.living_room_lamp, switch.garage_light
        
and restart Home Assistant. You should now be able to say "okay rhasspy"
followed by "switch on all the lights" or "switch off all the lights" and see it
happen in the web interface.
        
The `intent_script` portion defines how Home Assistant responds to the *intents*
that the `conversation` component recognizes (after `stt_pocketsphinx` decodes
your speech). The intent names and actions can be anything you want!
