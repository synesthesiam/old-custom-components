Training Workflow
=====================

When Rhasspy is installed, you can customize it by adding your own example
phrases and custom intents. Here how this is expected to work with the
`rasa_nlu` component:

1. You add new intents/phrases to `examples.md` in whatever language you have
   configured (English by default)
2. Run the `rhasspy_train.train` service. This will re-create `examples.lm`
   (custom language model) and mix it with your base language model into
   `mixed.lm`
3. Any unknown words have their pronunciations guessed and put in
   `unknown.dict`. You should review these and copy/correct them in `user.dict`
   (which is combined with the base dictionary into `mixed.dict`
4. Once there are no more unknown words, re-run `rhasspy_train.train` and
   restart Home Assistant

The training process trains both pocketsphinx and `rasa_nlu` (**only** if you
have `project_dir` and `rasa_config` set in `rhasspy_train`), so you only need
to edit `examples.md` when `rasa_nlu` is installed. 

When using Home Assistant's `conversation` component (from the Raspberry Pi
guide), you have to put phrases **both** in `examples.md` and
`configuration.yaml` under the `conversation` config. Additionally, you need to
spell out all of the possible values for each slot in a `conversation` phrase.
For example, the `conversaton` component automatically accepts phrases like
"turn on the garage light" and translates this into a `HassTurnOn` intent with
`name = "garage light"`. Rhasspy needs examples of every combination: "turn on
the garage light", "turn on the living room lamp", "turn off the garage light",
etc., because it trains the speech recognizer ahead of time.
