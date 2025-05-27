'''
Upload timeline png to the server for shijian
'''

import requests
import hashlib
import time
import json
import os

class TimelineUploader:
    def __init__(self, cfg_path):
        with open(cfg_path) as f:
            self.cfg = json.load(f)
        
        # resolve relative path in json
        cfg_dir = os.path.dirname(os.path.abspath(cfg_path))
        if not os.path.isabs(self.cfg['png_file']):
            self.cfg['png_file'] = os.path.normpath(
                os.path.join(os.path.dirname(cfg_dir), 'output', self.cfg['png_file']))
    
    def gen_auth_token(self):
        timestamp = str(int(time.time()))
        signature = hashlib.sha256(
            (self.cfg['api_key'] + timestamp).encode()
        ).hexdigest()
        return f"{timestamp}:{signature}"
    
    def upload_png(self):
        if not os.path.exists(self.cfg['png_file']):
            print(f"File not found: {self.cfg['png_file']}")
            return False
        # print(f'Trying to upload {self.cfg['png_file']}')

        auth_token = self.gen_auth_token()
        
        try:
            with open(self.cfg['png_file'], 'rb') as f:
                files = {'file': f}
                headers = {'Authorization': f'Bearer {auth_token}'}
                
                response = requests.post(
                    self.cfg['server_url'],
                    files=files,
                    headers=headers,
                    timeout=30
                )
                
            if response.status_code == 200:
                print("Upload successful")
                return True
            else:
                # parse json err msg
                try:
                    error_data = response.json()
                    error_msg = error_data.get('error', 'Unknown error')
                    print(f"Upload failed ({response.status_code}): {error_msg}")
                except:
                    print(f"Upload failed: {response.status_code}")
                return False
                
        except Exception as e:
            print(f"Error: {e}")
            return False

if __name__ == "__main__":
    uploader = TimelineUploader(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'cfg', 'upload_config.json'))
    uploader.upload_png()