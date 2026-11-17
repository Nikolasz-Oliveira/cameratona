from config.config_loader import Config
from core.analytics.strategy_interface import AnalyticsStrategy
from utils.logger import logger


class StrategyFactory:
    """Cria a estratégia de análise definida em analytics.strategy no settings.json."""

    @staticmethod
    def create_strategy() -> AnalyticsStrategy:
        name = str(Config.analytics.get("strategy", "line")).lower()
        logger.info(f"Estratégia de análise selecionada: '{name}'.")

        if name == "line":
            from core.analytics.line_strategy import LineStrategy
            return LineStrategy()

        raise ValueError(
            f"Estratégia '{name}' não suportada. Valores disponíveis: 'line'."
        )
