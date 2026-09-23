import json
import os

class ConfigLoader:
    def __init__(self, config_path="config/settings.json"):
        self.config_path = config_path
        self._config = self._load()

    def _load(self):
        if not os.path.exists(self.config_path):
            raise FileNotFoundError(f"Arquivo de configuracao nao encontrado: {self.config_path}")
        with open(self.config_path, 'r', encoding='utf-8') as f:
            return json.load(f)

    @property
    def camera(self):
        return self._config.get("camera", {})

    @property
    def ai(self):
        return self._config.get("ai", {})

    @property
    def analytics(self):
        return self._config.get("analytics", {})

    @property
    def ui(self):
        return self._config.get("ui", {})

    def get_rtsp_url(self):
        cam = self.camera
        endpoint = cam["sub_stream"] if cam.get("use_substream") else cam["main_stream"]
        if cam.get("user") and cam.get("password"):
            return f"rtsp://{cam['user']}:{cam['password']}@{cam['ip']}:{cam['port']}/{endpoint}"
        return f"rtsp://{cam['ip']}:{cam['port']}/{endpoint}"

# Instância global para ser importada pelos outros módulos
Config = ConfigLoader()