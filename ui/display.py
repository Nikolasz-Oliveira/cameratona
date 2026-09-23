import cv2

class Display:
    def __init__(self, window_name="Monitoramento de Fluxo"):
        self.window_name = window_name
        self.drawing = False
        self.temp_p1 = None
        self.new_line = None
        
        # Necessário criar a janela antes para atrelar o evento de mouse
        cv2.namedWindow(self.window_name)
        cv2.setMouseCallback(self.window_name, self._mouse_event)

    def _mouse_event(self, event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            self.drawing = True
            self.temp_p1 = (x, y)
            self.new_line = None
        elif event == cv2.EVENT_LBUTTONUP:
            self.drawing = False
            if self.temp_p1:
                self.new_line = (self.temp_p1, (x, y))

    def get_new_line(self):
        if self.new_line:
            line = self.new_line
            self.new_line = None
            return line
        return None

    def draw_elements(self, frame, p1, p2, entradas, saidas):
        if frame is None:
            return frame
            
        h, w = frame.shape[:2]
        cv2.line(frame, p1, p2, (0, 255, 255), 3)

        # Feedback visual enquanto arrasta o mouse
        if self.drawing and self.temp_p1:
            cv2.circle(frame, self.temp_p1, 5, (255, 0, 0), -1)

        # Textos movidos para o canto inferior esquerdo (h - margem)
        cv2.putText(frame, f"Entradas: {entradas}", (30, h - 80),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 255, 0), 2)
        cv2.putText(frame, f"Saidas: {saidas}", (30, h - 30),
                    cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 255), 2)
                    
        return frame

    def show(self, frame):
        if frame is not None:
            cv2.imshow(self.window_name, frame)

    def check_exit(self):
        return cv2.waitKey(1) & 0xFF == ord('q')

    def close(self):
        cv2.destroyAllWindows()