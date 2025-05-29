#!/usr/bin/env python3
import sys
import argparse
import os
from alarm import bark, Sound, SOUND_DIR

def main():
    parser = argparse.ArgumentParser(description='Test alarm sound playback')
    parser.add_argument('sound', nargs='?', default='DEFAULT', 
                       help='Sound name from enum or custom filename (without .wav)')
    parser.add_argument('--list', '-l', action='store_true',
                       help='List available sounds')
    
    args = parser.parse_args()
    
    if args.list:
        print("Available preset sounds:")
        for sound in Sound:
            sound_path = os.path.join(SOUND_DIR, sound.value + '.wav')
            exists = "✓" if os.path.exists(sound_path) or sound == Sound.BEEP else "✗"
            print(f"  {sound.name:<10} ({sound.value}) {exists}")
        return
    
    # Try to get enum by name, fallback to direct value
    try:
        sound = Sound[args.sound.upper()]
    except KeyError:
        sound = args.sound
    
    try:
        print(f"Playing sound: {sound}")
        bark(sound)
        input("Press Enter to exit...")
        
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()