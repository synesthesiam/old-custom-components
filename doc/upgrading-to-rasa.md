Upgrading to RasaNLU
=========================

If you've followed the [detailed Raspberry Pi
guide](https://github.com/synesthesiam/rhasspy-assistant/blob/master/doc/detailed-rpi.md),
you'll be using Home Assistant's built in [conversation
component](https://www.home-assistant.io/components/conversation/). To get the
full Rhasspy experience, you'll want to "upgrade" to using the `rasa_nlu`
component. [RasaNLU](https://nlu.rasa.com/) uses machine learning techniques and
the powerful [spaCy](https://spacy.io/) natural language processing library to
transform chat messages into intents (`conversation` uses regular expressions).

Modifying Your Configuration
-----------------------------------

To upgrade, you need to do four things:

1. Add a configuration for `rasa_nlu` component
2. Modify your `rhasspy_train` configuration
3. Update your `automations.yaml` file
4. Install a language model

### Add rasa_nlu Configuration

First, edit your `configuration.yaml` file and add the following text:


    # Recognize intents with rasaNLU.
    rasa_nlu:
      project_dir: $RHASSPY_ASSISTANT/data/projects
      
Replace `$RHASSPY_ASSISTANT` with the path to your cloned `rhasspy_assistant`
repository. Note: you do **not** have to delete your `conversation`
configuration block.

### Modify rhasspy_train

Next, find the `rhasspy_train` configuration block in `configuration.yaml` and
add these two lines:

    rhasspy_train:
      ...  # the rest of your configuration
      rasa_config: $RHASSPY_ASSISTANT/etc/rasa/config_spacy.yml
      project_dir: $RHASSPY_ASSISTANT/data/projects
      project_name: rhasspy

Replace `$RHASSPY_ASSISTANT` with the path to your cloned `rhasspy_assistant`
repository.

### Update automations.yaml

Finally, edit `automations.yaml` and find the automation that handles the
`speech_to_text` event. It should look like this initially:

    - alias: "speech to text -> intent recognition"
      trigger:
        platform: event
        event_type: speech_to_text
      action:
        - service: conversation.process
          data_template:
            text: "{{ trigger.event.data['text'] }}"
            
Edit this automation to call the `rasa_nlu.parse` service instead of
`conversation.process`:

    - alias: "speech to text -> intent recognition"
      trigger:
        platform: event
        event_type: speech_to_text
      action:
        - service: rasa_nlu.parse
          data_template:
            message: "{{ trigger.event.data['text'] }}"
            project: rhasspy

The `project` here should match the `project_name` in your `rhasspy_train`
configuration.

### Install a Language Model

Go ahead and restart Home Assistant. Watch the log and make sure all of the
dependencies are installed correctly. The `spaCy` library can be especially
demanding on the Raspberry Pi, and may require increasing your swap size. If the
installation fails, try doing this:

1. Edit `/etc/dphys-swapfile` with `sudo`
2. Increase `CONF_SWAPSIZE` to something like `1024` or `2048` depending on the
   size of your SD card (higher is better)
3. Restart the Raspberry Pi

Once `spaCy` has successfully been installed, you'll need to install a language model:

    cd /home/pi/homeassistant
    source bin/activate
    python3 -m spacy download en
    
If your using a language other than English, replace `en` with [one of the
supported languages](https://spacy.io/models/).
    
### Re-train Rhasspy

Everything should be ready now. Go ahead and call the `rhasspy_train.train`
service from the services tab in Home Assistant. If there are no errors in the
log, restart Home Assistant to start using `rasa_nlu`. Rhasspy is now using the
intents and phrases in `examples.md`. See the [training
workflow](https://github.com/synesthesiam/rhasspy-assistant/blob/master/doc/training-workflow.md)
for more information.
