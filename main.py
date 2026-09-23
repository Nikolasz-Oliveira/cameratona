import time
import threading
import cv2
from core.video.rtsp_stream import RTSPStream
from core.video.renderer import Renderer
from core.ai.model_factory import DetectorFactory
from core.analytics.line_strategy import LineStrategy
from utils.logger import logger

class CameratonaApp:
    def __init__(self):
        self.detector = None
        self.ia_carregando = True
        self.stream = None
        self.renderer = None
        self.strategy = None

    def _iniciar_ia_e_regras(self):
        logger.info("Iniciando carregamento da IA em segundo plano...")
        self.detector = DetectorFactory.create_detector()
        # Aqui, futuramente, utilizaremos uma StrategyFactory baseada no JSON
        self.strategy = LineStrategy() 
        self.ia_carregando = False
        logger.info("Sistema de análise pronto.")

    def iniciar(self):
        try:
            self.stream = RTSPStream().start()
        except Exception as e:
            logger.error(f"Falha crítica na rede: {e}")
            return

        self.renderer = Renderer()
        threading.Thread(target=self._iniciar_ia_e_regras, daemon=True).start()

        try:
            while True:
                ret, frame = self.stream.read()

                if not ret or frame is None:
                    time.sleep(0.01)
                    continue

                if self.ia_carregando:
                    cv2.putText(frame, "Inicializando IA. Aguarde...", (20, 40), 
                                cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                    self.renderer.show(frame)
                else:
                    annotated_frame, detections = self.detector.process_frame(frame)
                    
                    # Intercepta novos desenhos feitos pelo mouse
                    nova_geom = self.renderer.get_new_geometry()
                    if nova_geom:
                        self.strategy.set_geometry(nova_geom)
                    
                    self.strategy.update(detections)
                    
                    entradas, saidas = self.strategy.get_stats()
                    geom = self.strategy.get_geometry()
                    
                    final_frame = self.renderer.draw(annotated_frame, geom, entradas, saidas)
                    self.renderer.show(final_frame)

                # Verifica eventos de teclado e controle de encerramento
                if self.renderer.check_keys() == 'quit':
                    logger.info("Encerramento solicitado pelo usuário.")
                    break
                    
        finally:
            logger.info("Encerrando serviços e liberando recursos...")
            if self.stream:
                self.stream.stop()
            if self.renderer:
                self.renderer.close()

if __name__ == "__main__":
    CameratonaApp().iniciar()