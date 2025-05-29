import os
import threading, platform
from enum import Enum

SOUND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'sound')

class Sound(Enum):
    DEFAULT = 'default'
    _173 = '173'
    A = 'A'                 # .- .-
    US = 'US'               # ..- ...
    UPRISING = 'uprising'
    CALM = 'calm'
    SNEAKY = 'sneaky'
    HUMOR = 'humor'
    EWMF = 'EWMF'     
    BEEP = '?'      

def bark(sound:Sound=Sound.DEFAULT):
    aud_thread = threading.Thread(target=_play, args=(sound,))
    aud_thread.daemon = True
    aud_thread.start()

def _play(sound:Sound=Sound.DEFAULT):
    '''sync play; direct calls block main thread'''
    if isinstance(sound, Sound):
        if sound == Sound.BEEP:
            print('\a')
            return
        sound_name = sound.value
    else:
        sound_name = sound

    sound_path = os.path.join(SOUND_DIR, sound_name + '.wav')
    if not os.path.exists(sound_path):
        raise FileNotFoundError(f'Cannot find sound file: {sound_name}')
    
    s = platform.system()
    if s == 'Windows':
        try:
            import winsound
            winsound.PlaySound(sound_path, winsound.SND_FILENAME)
            return
        except ImportError:
            pass 
    elif s == 'Linux':
        os.system(f'aplay "{sound_path}" 2>/dev/null')
    else:
        print('Where the hell are you running this??')
        print('\a') # unhappy beep

