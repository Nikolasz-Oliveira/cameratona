import json
import os

class CameraConfig:
    def __init__(self, config_file="camera_config.json"):
        self.config_file = config_file
        self.settings = self._load_or_create()

    def _load_or_create(self):
        # Cria um JSON padrão caso o arquivo não exista
        if not os.path.exists(self.config_file):
            default = {
                "ip": "192.168.1.110",
                "port": 554,
                "user": "",
                "password": "",
                "main_stream": "onvif1",
                "sub_stream": "onvif2"
            }
            with open(self.config_file, 'w') as f:
                json.dump(default, f, indent=4)
            return default
        
        with open(self.config_file, 'r') as f:
            return json.load(f)

    def get_rtsp_url(self, quality="x"):
        ip = self.settings["ip"]
        port = self.settings["port"]
        user = self.settings["user"]
        password = self.settings["password"]
        
        endpoint = self.settings["sub_stream"] if quality == "sub" else self.settings["main_stream"]
        
        if user and password:
            return f"rtsp://{user}:{password}@{ip}:{port}/{endpoint}"
        return f"rtsp://{ip}:{port}/{endpoint}"