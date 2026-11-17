import logging
import time
from datetime import date
from pathlib import Path

# Pasta de logs sempre na raiz do projeto, independente de onde o programa é executado
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)
LOG_RETENTION_DAYS = 60


class DailyFileHandler(logging.FileHandler):
    """
    Grava em logs/fluxo_AAAA-MM-DD.log e troca de arquivo à meia-noite, mesmo com o
    programa rodando por vários dias (modo serviço). Apaga logs com mais de
    LOG_RETENTION_DAYS dias.
    """

    def __init__(self):
        self._day = date.today()
        super().__init__(self._path_for(self._day), encoding="utf-8")
        self._cleanup()

    @staticmethod
    def _path_for(day):
        return LOG_DIR / f"fluxo_{day.isoformat()}.log"

    def emit(self, record):
        today = date.today()
        if today != self._day:
            self.acquire()
            try:
                self._day = today
                if self.stream:
                    self.stream.close()
                    self.stream = None
                self.baseFilename = str(self._path_for(today))
            finally:
                self.release()
            self._cleanup()
        super().emit(record)

    @staticmethod
    def _cleanup():
        limite = time.time() - LOG_RETENTION_DAYS * 86400
        for f in LOG_DIR.glob("fluxo_*.log"):
            try:
                if f.stat().st_mtime < limite:
                    f.unlink()
            except OSError:
                pass


# Configuração base do logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        DailyFileHandler(),
        logging.StreamHandler() # Também joga para o console
    ]
)

# Exporta a instância pronta para uso
logger = logging.getLogger("cameratona")
