import cv2
import numpy as np
from config.config_loader import Config


class Renderer:
    def __init__(self):
        self.window_name = Config.ui.get("window_name", "Cameratona Analytics")
        self.text_color = tuple(Config.ui.get("colors", {}).get("text", [255, 255, 255]))
        self.geom_color = tuple(Config.ui.get("colors", {}).get("line", [0, 255, 255]))

        self.temp_points = []
        self.new_geometry = None
        self.last_frame_shape = (720, 1280, 3)

        cv2.namedWindow(self.window_name)
        cv2.setMouseCallback(self.window_name, self._mouse_event)

    def _mouse_event(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.temp_points.append([x, y])
        elif event == cv2.EVENT_RBUTTONDOWN:
            if self.temp_points:
                self.temp_points.pop() # Desfaz o último clique

    def get_new_geometry(self):
        if self.new_geometry:
            geom = self.new_geometry
            self.new_geometry = None
            return geom
        return None

    def draw(self, frame, geometry, entradas, saidas, entry_arrow=None):
        if frame is None:
            return frame

        h, w = frame.shape[:2]

        # Desenha a geometria ativa (Linha ou Polígono)
        if len(geometry) == 2:
            cv2.line(frame, tuple(map(int, geometry[0])), tuple(map(int, geometry[1])), self.geom_color, 3)
        elif len(geometry) > 2:
            pts = np.array(geometry, np.int32).reshape((-1, 1, 2))
            cv2.polylines(frame, [pts], isClosed=True, color=self.geom_color, thickness=3)

        # Seta indicando o sentido considerado ENTRADA
        if entry_arrow is not None:
            start, end = entry_arrow
            cv2.arrowedLine(frame, start, end, self.geom_color, 2, tipLength=0.35)
            cv2.putText(frame, "ENTRADA", (end[0] + 5, end[1]),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, self.geom_color, 1)

        self.draw_drawing_overlay(frame)

        # Informações de fluxo
        cv2.putText(frame, f"Entradas: {entradas}", (30, h - 80), cv2.FONT_HERSHEY_SIMPLEX, 1, self.text_color, 2)
        cv2.putText(frame, f"Saidas: {saidas}", (30, h - 30), cv2.FONT_HERSHEY_SIMPLEX, 1, self.text_color, 2)

        return frame

    def draw_drawing_overlay(self, frame):
        """Desenha o "rascunho" enquanto o usuário está clicando na tela."""
        if not self.temp_points:
            return frame
        for p in self.temp_points:
            cv2.circle(frame, tuple(p), 5, (0, 0, 255), -1)
        if len(self.temp_points) > 1:
            pts = np.array(self.temp_points, np.int32).reshape((-1, 1, 2))
            cv2.polylines(frame, [pts], isClosed=False, color=(0, 0, 255), thickness=2)
        cv2.putText(frame, "Desenhando... [Espaco] Confirma | [C] Limpa", (30, 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        return frame

    def no_signal_frame(self, message="Sem sinal da camera - reconectando..."):
        """Frame preto com aviso, usado quando a câmera para de enviar imagens."""
        frame = np.zeros(self.last_frame_shape, dtype=np.uint8)
        cv2.putText(frame, message, (30, 60), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 2)
        return frame

    def show(self, frame):
        if frame is not None:
            self.last_frame_shape = frame.shape
            cv2.imshow(self.window_name, frame)

    def check_keys(self):
        """Retorna 'quit', 'invert' ou None. Lida internamente com a captura de geometria."""
        key = cv2.waitKey(1) & 0xFF
        if key == ord('q'):
            return 'quit'
        elif key == ord('i'):
            return 'invert'
        elif key == ord('c'):
            self.temp_points = [] # Cancela o desenho atual
        elif key == 32 or key == 13: # Espaço ou Enter
            if len(self.temp_points) >= 2:
                self.new_geometry = self.temp_points.copy()
                self.temp_points = []
        return None

    def close(self):
        cv2.destroyAllWindows()
