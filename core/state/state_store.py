"""
Guarda o estado que precisa sobreviver a reinícios (ex.: totais de entradas/saídas).

O arquivo é gravado de forma atômica (escreve num temporário e substitui), então
uma queda de energia no meio da gravação não corrompe o estado anterior.
"""
import json
import os
from pathlib import Path

from utils.logger import logger

PROJECT_ROOT = Path(__file__).resolve().parent.parent.parent
DEFAULT_STATE_PATH = PROJECT_ROOT / "data" / "estado.json"


class StateStore:
    def __init__(self, path=DEFAULT_STATE_PATH):
        self.path = Path(path)

    def load(self) -> dict:
        if not self.path.exists():
            logger.info(f"Nenhum estado salvo em {self.path}. Começando do zero.")
            return {}
        try:
            with open(self.path, "r", encoding="utf-8") as f:
                state = json.load(f)
            logger.info(f"Estado restaurado de {self.path}.")
            return state
        except (OSError, json.JSONDecodeError) as e:
            # Não apaga o arquivo: guarda uma cópia para análise e começa do zero
            backup = self.path.with_suffix(".corrompido.json")
            try:
                os.replace(self.path, backup)
            except OSError:
                pass
            logger.error(f"Estado salvo ilegível ({e}). Cópia em {backup}. Começando do zero.")
            return {}

    def save(self, state: dict):
        try:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            tmp = self.path.with_suffix(".tmp")
            with open(tmp, "w", encoding="utf-8") as f:
                json.dump(state, f, ensure_ascii=False, indent=2)
                f.flush()
                os.fsync(f.fileno())
            os.replace(tmp, self.path)
        except OSError as e:
            logger.error(f"Não foi possível salvar o estado em {self.path}: {e}")
