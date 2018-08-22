FROM homeassistant/home-assistant
LABEL maintainer="Michael Hansen <hansen.mike@gmail.com>"

VOLUME /config
VOLUME /assistant
VOLUME /tools

RUN apt-get update && apt-get install -y git build-essential \
        python3-dev \
        libasound2-dev libpulse-dev swig \
        portaudio19-dev \
        libatlas-dev libatlas-base-dev \
        libtcl8.6 \
        espeak alsa-utils

COPY deps/* /root/deps/

RUN pip3 install --no-cache-dir \
    /root/deps/num2words-0.5.7.tar.gz \
    /root/deps/pocketsphinx-0.1.15.tar.gz \
    /root/deps/PyAudio-0.2.11.tar.gz \
    /root/deps/pyttsx3-2.7-py3-none-any.whl \
    /root/deps/v1.3.0.tar.gz \
    /root/deps/webrtcvad-2.0.10.tar.gz

#RUN pip3 install --no-cache-dir pyaudio pocketsphinx \
#        webrtcvad \
#        pyttsx3 incremental num2words \
#        https://github.com/Kitt-AI/snowboy/archive/v1.3.0.tar.gz

#RUN python -m spacy download en
    
CMD [ "python", "-m", "homeassistant", "--config", "/config" ]
