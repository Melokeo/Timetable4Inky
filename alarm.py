import os
import threading, platform
from enum import Enum
from subprocess import Popen

SOUND_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'resources', 'sound')
curr_aplay_handle: Popen = None    # for stopping curr sound play from btn

class Sound(Enum):      
    '''  internal name = "filename"  '''
    DEFAULT = 'default'
    _173 = '173'
    A = 'A'                 # .- .-
    US = 'US'               # ..- ...
    UPRISING = 'uprising'   # perhaps
    CALM = 'calm'
    SNEAKY = 'sneaky'
    HUMOR = 'humor'
    EWMF = 'EWMF'     
    BEEP = '?' 
    TRIANGLE_1 = 'triangle1'   # dlleng~~~~     
    OB_STAC = 'ob_stac'   # G#-E

def bark(sound:Sound=Sound.DEFAULT):
    print(f':BARKING: [{sound}]')
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
        global curr_aplay_handle
        try:
            curr_aplay_handle = Popen(['aplay', sound_path])
            curr_aplay_handle.wait()
        except Exception as e:
            print(f'Failed to play sound: {e}')
        finally:
            curr_aplay_handle = None
    else:
        print('Where the hell are you running this??')
        print('\a') # unhappy beep

def shut_up():
    global curr_aplay_handle
    if curr_aplay_handle and curr_aplay_handle.poll() is None:
        curr_aplay_handle.terminate()
        curr_aplay_handle = None
        print('Stopped sound.')

