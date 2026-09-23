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