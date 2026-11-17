from abc import ABC, abstractmethod


class AnalyticsStrategy(ABC):
    @abstractmethod
    def update(self, detections):
        pass

    @abstractmethod
    def get_stats(self):
        pass

    @abstractmethod
    def get_geometry(self):
        pass

    @abstractmethod
    def set_geometry(self, points):
        """Recebe uma lista de pontos [x, y] do Renderer e atualiza a regra"""
        pass

    # ------------------------------------------------------------------ persistência
    def export_state(self) -> dict:
        """Estado a ser salvo em disco (ex.: totais). Padrão: nada."""
        return {}

    def restore_state(self, state: dict):
        """Restaura o que export_state() devolveu numa execução anterior."""
        pass

    # ------------------------------------------------------------------ eventos
    # Quem quiser ser avisado de eventos (ex.: envio ao ThingsBoard) se registra
    # aqui. A estratégia não precisa saber para onde os eventos vão.
    def add_listener(self, callback):
        """callback(evento: dict) é chamado a cada evento gerado pela estratégia."""
        if not hasattr(self, "_listeners"):
            self._listeners = []
        self._listeners.append(callback)

    def _emit(self, event):
        for callback in getattr(self, "_listeners", []):
            try:
                callback(event)
            except Exception:
                # Um destino com problema nunca pode derrubar a análise
                from utils.logger import logger
                logger.exception("Erro ao repassar evento da estratégia.")
