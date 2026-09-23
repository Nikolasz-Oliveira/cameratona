import time
import threading
import cv2
from core.config import CameraConfig
from core.video_stream import VideoStream
from core.business_logic import LineCounter
from ui.display import Display

class Aplicacao:
    def __init__(self):
        self.detector = None
        self.ia_carregando = True
        # Pontos da linha virtual (ajuste conforme a posição da porta no vídeo)
        self.p1 = (1100, 530)
        self.p2 = (1290, 545)
        self.counter = LineCounter(self.p1, self.p2)

    def _carregar_ia(self):
        from core.detector import YoloDetector
        # Confirme se o arquivo yolov8n.pt está na raiz para uso offline
        self.detector = YoloDetector(model_path="yolov8n.pt")
        self.ia_carregando = False

    def iniciar(self):
        config = CameraConfig()
        RTSP_URL = config.get_rtsp_url()

        print("Conectando à câmera...")
        try:
            stream = VideoStream(RTSP_URL).start()
        except Exception as e:
            print(f"Erro ao iniciar o stream: {e}")
            return

        display = Display("Contagem de Fluxo - YOLOv8")
        threading.Thread(target=self._carregar_ia, daemon=True).start()

        try:
            while True:
                ret, frame = stream.read()

                if not ret or frame is None:
                    time.sleep(0.01)
                    continue

                if self.ia_carregando:
                    cv2.putText(frame, "Carregando IA na GPU...", (20, 40), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                    display.show(frame)
                else:
                    # Verifica se o usuário desenhou uma nova linha com o mouse
                    nova_linha = display.get_new_line()
                    if nova_linha:
                        self.p1, self.p2 = nova_linha
                        self.counter.update_line(self.p1, self.p2)
                        print(f"Nova linha configurada: {self.p1} -> {self.p2}")

                    annotated_frame, detections = self.detector.process_frame(frame)
                    self.counter.update(detections)
                    
                    final_frame = display.draw_elements(
                        annotated_frame, self.p1, self.p2, 
                        self.counter.entradas, self.counter.saidas
                    )
                    display.show(final_frame)

                if display.check_exit():
                    break
                    
        finally:
            print("\nEncerrando serviços de forma segura...")
            stream.stop()
            display.close()

if __name__ == "__main__":
    Aplicacao().iniciar()