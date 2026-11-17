import logging
from datetime import datetime
from pathlib import Path

# Pasta de logs sempre na raiz do projeto, independente de onde o programa é executado
LOG_DIR = Path(__file__).resolve().parent.parent / "logs"
LOG_DIR.mkdir(exist_ok=True)

# Define o nome do arquivo baseado no dia atual
log_filename = LOG_DIR / datetime.now().strftime("fluxo_%Y-%m-%d.log")

# Configuração base do logger
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
    handlers=[
        logging.FileHandler(log_filename, encoding='utf-8'),
        logging.StreamHandler() # Também joga para o console
    ]
)

# Exporta a instância pronta para uso
logger = logging.getLogger("cameratona")
