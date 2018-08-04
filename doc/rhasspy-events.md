Rhasspy Events
==================

This is a quick guide to the events Rhasspy uses inside Home Assistant. You can
inject these events either through the Home Assistant web front end (click the
little radio tower looking button under Developer Tools), or via the command
line with the [REST
API](https://developers.home-assistant.io/docs/en/external_api_rest.html).

This guide assumes you have Rhasspy already set up, and any commands are
executed on the computer that Home Assistant is running on (e.g., on the
Raspberry Pi itself).

Event Flow
------------

Let's look at a typical event flow for Rhasspy when things are working
correctly:

1. A hotword service (like `hotword_snowboy`) starts listening
2. When the hotword is heard, a `hotword_detected` event is fired
3. The `stt_pocketsphinx` service catches this event and starts listening for commands
4. When the command is finished (after some silence), a `speech_recorded` event is fired
5. Once `stt_pocketsphinx` has finished decoding the audio data, a
   `speech_to_text` event is fired with a `text` property, and the hotword
   service begins listening again
6. An intent recognition service, like `conversation` or `rasa_nlu` catches this
   event and parses the text
7. The parsed intent is fired using Home Assistant's [intent
   system](https://developers.home-assistant.io/docs/en/intent_index.html)
8. The `intent_script` component runs a script to handle the intent

Most of this behavior is controlled using Home Assistant
[automations](https://www.home-assistant.io/components/automation/) In every
Rhasspy [configuration
example](https://github.com/synesthesiam/rhasspy-assistant/tree/master/config/examples),
the `automations.yaml` file controls how events and data are passed between
Rhasspy's custom components and Home Assistant. The `automations.yaml` from the
[Raspberry Pi
example](https://github.com/synesthesiam/rhasspy-assistant/tree/master/config/examples/raspberry_pi)
starts with the following text:

```
- alias: "start hotword"
  trigger:
    platform: homeassistant
    event: start
  action:
    service: hotword_snowboy.listen
```

This starts the `hotword_snowboy` service listening for "okay rhasspy", or
whatever your model is configured to listen for when Home Assistant first starts.

The next block:

```
- alias: "hotword -> speech to text"
  trigger:
    platform: event
    event_type: hotword_detected
  action:
    - service: wav_aplay.play_wav
      data:
        filename: $RHASSPY_ASSISTANT/etc/wav/wakeup.wav
    - service: stt_pocketsphinx.listen
```

plays a WAV file when the hotword is detected and starts `stt_pocketsphinx`
listening. If you want to test a command without saying the hotword, you can
simply inject the `hotword_detected` event and jump right to this step:

    curl -X POST -s http://localhost:8123/api/events/hotword_detected
    
You should hear a beep and be able to speak a command. If you'd like to use a
pre-recorded command, it's pretty simple. First, record a WAV file (maybe with
`arecord`), then simply POST it to the `stt_pocketsphinx` component:

    curl -X POST -s -H 'Content-Type: audio/wav' --data-binary @my-command.wav http://localhost:8123/api/stt_pocketsphinx
    
The next part of `automations.yaml` is:

```
- alias: "speech to text working"
  trigger:
    platform: event
    event_type: speech_recorded
  action:
    - service: wav_aplay.play_wav
      data:
        filename: $RHASSPY_ASSISTANT/etc/wav/command_recorded.wav
    - service: hotword_snowboy.listen
```

This simply plays a WAV file to let you know your command has been recorded and
starts the hotword service listening again. The next block, however:

```
- alias: "speech to text -> intent recognition"
  trigger:
    platform: event
    event_type: speech_to_text
  action:
    - service: conversation.process
      data_template:
        text: "{{ trigger.event.data['text'] }}"
```

handles the results of the speech recognition. The `speech_to_text` event from
`stt_pocketsphinx` contains a `text` property that gets passed to the intent
recognizer (which is just Home Assistant's [conversation
component](https://www.home-assistant.io/components/conversation/) here).
Injecting this event is straightforward:

    curl -X POST -s -H 'Content-Type: application/json' -d '{ "text": "turn off the garage light" }' http://localhost:8123/api/events/speech_to_text
    
Of course, you could just call the `conversation.process` service directly too.
Doing either should trigger any scripts you have in `intent_script`. And now you
are able to manipulate each part of Rhasspy independently!
