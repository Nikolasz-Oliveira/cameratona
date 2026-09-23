from abc import ABC, abstractmethod

class BaseDetector(ABC):
    @abstractmethod
    def process_frame(self, frame):
        """
        Recebe um frame OpenCV (numpy array).
        Deve retornar uma tupla: (frame_anotado, lista_de_deteccoes).
        Formato de deteccao: {"id": int, "bbox": (x1,y1,x2,y2), "foot_point": (x,y)}
        """
        pass