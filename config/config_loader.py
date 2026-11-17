import json
import os
from pathlib import Path

# Raiz do projeto (pasta que contém main.py). Usada para que o programa
# funcione independentemente da pasta de onde for executado.
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG_PATH = PROJECT_ROOT / "config" / "settings.json"
LOCAL_CONFIG_PATH = PROJECT_ROOT / "config" / "settings.local.json"


def _deep_merge(base: dict, override: dict) -> dict:
    """Mescla 'override' sobre 'base' recursivamente (sem alterar os originais)."""
    result = dict(base)
    for key, value in override.items():
        if isinstance(value, dict) and isinstance(result.get(key), dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


class ConfigLoader:
    """
    Ordem de prioridade (a última vence):
      1. config/settings.json        -> versionado no git, sem segredos
      2. config/settings.local.json  -> opcional, ignorado pelo git (credenciais, IP local...)
      3. Variáveis de ambiente CAMERATONA_CAM_USER / CAMERATONA_CAM_PASSWORD
    """

    def __init__(self, config_path=DEFAULT_CONFIG_PATH, local_path=LOCAL_CONFIG_PATH):
        self.config_path = Path(config_path)
        self.local_path = Path(local_path)
        self._config = self._load()

    def _load(self):
        if not self.config_path.exists():
            raise FileNotFoundError(f"Arquivo de configuracao nao encontrado: {self.config_path}")
        with open(self.config_path, "r", encoding="utf-8") as f:
            config = json.load(f)

        if self.local_path.exists():
            with open(self.local_path, "r", encoding="utf-8") as f:
                config = _deep_merge(config, json.load(f))

        cam = config.setdefault("camera", {})
        if os.environ.get("CAMERATONA_CAM_USER"):
            cam["user"] = os.environ["CAMERATONA_CAM_USER"]
        if os.environ.get("CAMERATONA_CAM_PASSWORD"):
            cam["password"] = os.environ["CAMERATONA_CAM_PASSWORD"]

        return config

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

    def _build_rtsp_url(self, mask_password=False):
        cam = self.camera
        endpoint = cam["sub_stream"] if cam.get("use_substream") else cam["main_stream"]
        if cam.get("user") and cam.get("password"):
            password = "****" if mask_password else cam["password"]
            return f"rtsp://{cam['user']}:{password}@{cam['ip']}:{cam['port']}/{endpoint}"
        return f"rtsp://{cam['ip']}:{cam['port']}/{endpoint}"

    def get_rtsp_url(self):
        return self._build_rtsp_url(mask_password=False)

    def get_rtsp_url_safe(self):
        """Mesma URL, mas com a senha mascarada (para usar em logs)."""
        return self._build_rtsp_url(mask_password=True)

    def resolve_path(self, path):
        """Resolve um caminho relativo à raiz do projeto, se o arquivo existir lá."""
        p = Path(path)
        if not p.is_absolute() and (PROJECT_ROOT / p).exists():
            return str(PROJECT_ROOT / p)
        return str(path)


# Instância global para ser importada pelos outros módulos
Config = ConfigLoader()
