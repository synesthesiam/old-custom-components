#!/usr/bin/env python3

import pprint
import pyaudio

def main():
    audio = pyaudio.PyAudio()
    print('')
    for i in range(audio.get_device_count()):
        info = audio.get_device_info_by_index(i)
        banner = 'Device %s (%s)' % (i, info['name'])
        print(banner)
        print('-' * len(banner))
        pprint.pprint(info)
        print('')

if __name__ == '__main__':
    main()
