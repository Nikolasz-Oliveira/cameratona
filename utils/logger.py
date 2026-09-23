import logging
import os
from datetime import datetime

# Garante que a pasta de logs exista
os.makedirs("logs", exist_ok=True)

# Define o nome do arquivo baseado no dia atual
log_filename = datetime.now().strftime("logs/fluxo_%Y-%m-%d.log")

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