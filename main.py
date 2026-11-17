import time
import threading
from core.video.rtsp_stream import RTSPStream
from core.video.renderer import Renderer
from core.ai.model_factory import DetectorFactory
from core.analytics.strategy_factory import StrategyFactory
from core.integrations.thingsboard_client import create_thingsboard_client
from config.config_loader import Config
from utils.logger import logger
import cv2


class CameratonaApp:
    def __init__(self):
        self.detector = None
        self.ia_carregando = True
        self.ia_erro = None
        self.stream = None
        self.renderer = None
        self.strategy = None
        self.no_signal_after_s = float(Config.camera.get("no_signal_after_s", 2))

        # Integração ThingsBoard (vira um cliente "nulo" se estiver sem token)
        self.tb = None
        self.summary_interval_s = float(Config.thingsboard.get("summary_interval_s", 10))
        self._last_summary = time.monotonic()
        self._frames_processados = 0
        self._pessoas_na_cena = 0

    def _iniciar_ia_e_regras(self):
        logger.info("Iniciando carregamento da IA em segundo plano...")
        try:
            self.detector = DetectorFactory.create_detector()
            self.strategy = StrategyFactory.create_strategy()
            self.strategy.add_listener(self._on_evento)
            self._enviar_atributos()
            self.ia_carregando = False
            logger.info("Sistema de análise pronto.")
        except Exception as e:
            self.ia_erro = str(e)
            logger.exception(f"Falha ao carregar IA/estratégia: {e}")

    # ------------------------------------------------------------------ ThingsBoard
    def _on_evento(self, evento):
        """Evento da estratégia (ENTRADA/SAIDA) -> telemetria com o horário do evento."""
        valores = {k: v for k, v in evento.items() if k != "ts"}
        self.tb.send_telemetry(valores, ts_ms=int(evento["ts"] * 1000))

    def _enviar_atributos(self):
        atributos = {
            "camera_ip": Config.camera.get("ip"),
            "modelo_ia": Config.ai.get("model_name"),
            "estrategia": Config.analytics.get("strategy", "line"),
        }
        if self.strategy:
            atributos["geometria"] = [list(map(int, p)) for p in self.strategy.get_geometry()]
            if hasattr(self.strategy, "inverted"):
                atributos["direcao_invertida"] = self.strategy.inverted
        self.tb.send_attributes(atributos)

    def _enviar_resumo_periodico(self):
        agora = time.monotonic()
        intervalo = agora - self._last_summary
        if intervalo < self.summary_interval_s:
            return
        camera_online = not self._sem_sinal()
        valores = {
            "camera_online": camera_online,
            "ia_pronta": not self.ia_carregando and not self.ia_erro,
            "fps": round(self._frames_processados / intervalo, 1),
            "pessoas_na_cena": self._pessoas_na_cena if camera_online else 0,
        }
        if self.strategy and not self.ia_carregando:
            valores["entradas"], valores["saidas"] = self.strategy.get_stats()
        self.tb.send_telemetry(valores)
        self._last_summary = agora
        self._frames_processados = 0

    def _sem_sinal(self):
        """True se a câmera nunca enviou frame ou parou de enviar há algum tempo."""
        elapsed = self.stream.seconds_since_last_frame()
        return elapsed is None or elapsed > self.no_signal_after_s

    def iniciar(self):
        self.tb = create_thingsboard_client().start()
        # A conexão (e as reconexões) acontecem na thread do stream
        self.stream = RTSPStream().start()
        self.renderer = Renderer()
        threading.Thread(target=self._iniciar_ia_e_regras, daemon=True).start()

        try:
            while True:
                ret, frame = self.stream.read()

                if ret:
                    if self.ia_erro:
                        cv2.putText(frame, f"Erro na IA: {self.ia_erro}"[:90], (20, 40),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                        self.renderer.show(frame)
                    elif self.ia_carregando:
                        cv2.putText(frame, "Inicializando IA. Aguarde...", (20, 40),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
                        self.renderer.draw_drawing_overlay(frame)
                        self.renderer.show(frame)
                    else:
                        self._processar(frame)
                elif self._sem_sinal():
                    self.renderer.show(self.renderer.no_signal_frame())
                    time.sleep(0.05)
                else:
                    # Nenhum frame novo ainda: evita ocupar 100% da CPU
                    time.sleep(0.005)

                self._enviar_resumo_periodico()

                # Teclado é verificado SEMPRE, mesmo sem frames (janela não congela)
                acao = self.renderer.check_keys()
                if acao == 'quit':
                    logger.info("Encerramento solicitado pelo usuário.")
                    break
                elif acao == 'invert' and self.strategy and hasattr(self.strategy, "toggle_direction"):
                    self.strategy.toggle_direction()
                    self._enviar_atributos()

        finally:
            logger.info("Encerrando serviços e liberando recursos...")
            if self.stream:
                self.stream.stop()
            if self.renderer:
                self.renderer.close()
            if self.tb:
                self.tb.stop()

    def _processar(self, frame):
        annotated_frame, detections = self.detector.process_frame(frame)

        # Intercepta novos desenhos feitos pelo mouse
        nova_geom = self.renderer.get_new_geometry()
        if nova_geom:
            self.strategy.set_geometry(nova_geom)
            self._enviar_atributos()

        self.strategy.update(detections)
        self._frames_processados += 1
        self._pessoas_na_cena = len(detections)

        entradas, saidas = self.strategy.get_stats()
        geom = self.strategy.get_geometry()
        arrow = self.strategy.get_entry_arrow() if hasattr(self.strategy, "get_entry_arrow") else None

        final_frame = self.renderer.draw(annotated_frame, geom, entradas, saidas, entry_arrow=arrow)
        self.renderer.show(final_frame)


if __name__ == "__main__":
    CameratonaApp().iniciar()
