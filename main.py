import argparse
import signal
import threading
import time

from config.config_loader import Config
from core.ai.model_factory import DetectorFactory
from core.analytics.strategy_factory import StrategyFactory
from core.integrations.thingsboard_client import create_thingsboard_client
from core.state.state_store import StateStore
from core.video.rtsp_stream import RTSPStream
from utils.logger import logger


class CameratonaApp:
    def __init__(self, headless=False):
        self.headless = headless
        self.running = False

        self.detector = None
        self.ia_carregando = True
        self.ia_erro = None
        self.stream = None
        self.renderer = None
        self.strategy = None
        self.no_signal_after_s = float(Config.camera.get("no_signal_after_s", 2))

        # Totais que sobrevivem a reinícios
        self.state_store = StateStore()

        # Integração ThingsBoard (vira um cliente "nulo" se estiver sem token)
        self.tb = None
        self.summary_interval_s = float(Config.thingsboard.get("summary_interval_s", 10))
        self._last_summary = time.monotonic()
        self._frames_processados = 0
        self._pessoas_na_cena = 0

    # ------------------------------------------------------------------ inicialização
    def _iniciar_ia_e_regras(self):
        logger.info("Iniciando carregamento da IA em segundo plano...")
        try:
            self.detector = DetectorFactory.create_detector()
            strategy = StrategyFactory.create_strategy()
            strategy.restore_state(self.state_store.load())
            strategy.add_listener(self._on_evento)
            self.strategy = strategy
            self._enviar_atributos()
            self.ia_carregando = False
            logger.info("Sistema de análise pronto.")
        except Exception as e:
            self.ia_erro = str(e)
            logger.exception(f"Falha ao carregar IA/estratégia: {e}")

    def _salvar_estado(self):
        if self.strategy:
            self.state_store.save(self.strategy.export_state())

    # ------------------------------------------------------------------ eventos / ThingsBoard
    def _on_evento(self, evento):
        """Evento da estratégia (ENTRADA/SAIDA): salva os totais e envia ao ThingsBoard."""
        self._salvar_estado()
        valores = {k: v for k, v in evento.items() if k != "ts"}
        self.tb.send_telemetry(valores, ts_ms=int(evento["ts"] * 1000))

    def _enviar_atributos(self):
        atributos = {
            "camera_ip": Config.camera.get("ip"),
            "modelo_ia": Config.ai.get("model_name"),
            "estrategia": Config.analytics.get("strategy", "line"),
            "modo": "servico" if self.headless else "janela",
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
            if hasattr(self.strategy, "get_daily_stats"):
                valores["entradas_hoje"], valores["saidas_hoje"] = self.strategy.get_daily_stats()
        self.tb.send_telemetry(valores)
        self._last_summary = agora
        self._frames_processados = 0

    # ------------------------------------------------------------------ alterações pela tela
    def _nova_geometria(self, pontos):
        self.strategy.set_geometry(pontos)
        p1, p2 = [list(map(int, p)) for p in self.strategy.get_geometry()[:2]]
        # Salva no settings.local.json para valer também no próximo início (e no serviço)
        Config.save_local({"analytics": {"geometry": {"line_p1": p1, "line_p2": p2}}})
        logger.info("Nova linha salva em config/settings.local.json.")
        self._enviar_atributos()

    def _inverter_direcao(self):
        self.strategy.toggle_direction()
        Config.save_local({"analytics": {"invert_direction": self.strategy.inverted}})
        self._enviar_atributos()

    # ------------------------------------------------------------------ loop principal
    def _sem_sinal(self):
        """True se a câmera nunca enviou frame ou parou de enviar há algum tempo."""
        elapsed = self.stream.seconds_since_last_frame()
        return elapsed is None or elapsed > self.no_signal_after_s

    def parar(self, *_):
        if self.running:
            logger.info("Encerramento solicitado.")
        self.running = False

    def iniciar(self):
        self.running = True
        self.tb = create_thingsboard_client().start()
        # A conexão (e as reconexões) acontecem na thread do stream
        self.stream = RTSPStream().start()
        if not self.headless:
            from core.video.renderer import Renderer
            self.renderer = Renderer()
        else:
            logger.info("Modo serviço (sem janela). Para parar: Ctrl+C ou parar o serviço.")
        threading.Thread(target=self._iniciar_ia_e_regras, daemon=True).start()

        try:
            while self.running:
                if self.ia_erro and self.headless:
                    # Sem janela não há quem veja o erro: sai para o supervisor tentar de novo
                    raise RuntimeError(f"Falha ao carregar IA: {self.ia_erro}")

                ret, frame = self.stream.read()

                if ret:
                    if self.ia_erro or self.ia_carregando:
                        self._mostrar_status(frame)
                    else:
                        self._processar(frame)
                elif self._sem_sinal():
                    if self.renderer:
                        self.renderer.show(self.renderer.no_signal_frame())
                    time.sleep(0.05)
                else:
                    # Nenhum frame novo ainda: evita ocupar 100% da CPU
                    time.sleep(0.005)

                self._enviar_resumo_periodico()

                if self.renderer:
                    # Teclado é verificado SEMPRE, mesmo sem frames (janela não congela)
                    acao = self.renderer.check_keys()
                    if acao == 'quit':
                        self.parar()
                    elif acao == 'invert' and self.strategy and hasattr(self.strategy, "toggle_direction"):
                        self._inverter_direcao()

        finally:
            logger.info("Encerrando serviços e liberando recursos...")
            self._salvar_estado()
            if self.stream:
                self.stream.stop()
            if self.renderer:
                self.renderer.close()
            if self.tb:
                self.tb.stop()
            logger.info("Encerrado.")

    def _mostrar_status(self, frame):
        if not self.renderer:
            return
        import cv2
        if self.ia_erro:
            cv2.putText(frame, f"Erro na IA: {self.ia_erro}"[:90], (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
        else:
            cv2.putText(frame, "Inicializando IA. Aguarde...", (20, 40),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 255), 2)
            self.renderer.draw_drawing_overlay(frame)
        self.renderer.show(frame)

    def _processar(self, frame):
        annotated_frame, detections = self.detector.process_frame(frame)

        if self.renderer:
            # Intercepta novos desenhos feitos pelo mouse
            nova_geom = self.renderer.get_new_geometry()
            if nova_geom:
                self._nova_geometria(nova_geom)

        self.strategy.update(detections)
        self._frames_processados += 1
        self._pessoas_na_cena = len(detections)

        if self.renderer:
            entradas, saidas = self.strategy.get_stats()
            hoje = self.strategy.get_daily_stats() if hasattr(self.strategy, "get_daily_stats") else None
            geom = self.strategy.get_geometry()
            arrow = self.strategy.get_entry_arrow() if hasattr(self.strategy, "get_entry_arrow") else None
            final_frame = self.renderer.draw(annotated_frame, geom, entradas, saidas,
                                             entry_arrow=arrow, hoje=hoje)
            self.renderer.show(final_frame)


def _parse_args():
    parser = argparse.ArgumentParser(description="Cameratona - contagem de pessoas por câmera IP")
    parser.add_argument("--headless", action="store_true",
                        help="roda sem janela (modo serviço); também ativável com ui.show_window=false")
    return parser.parse_args()


RESTART_DELAY_S = 30


def main():
    args = _parse_args()
    headless = args.headless or not Config.ui.get("show_window", True)

    parada_pedida = threading.Event()
    app = None

    def ao_receber_sinal(*_):
        parada_pedida.set()
        if app:
            app.parar()

    # Encerramento limpo (salva estado, envia o que falta ao ThingsBoard)
    signal.signal(signal.SIGINT, ao_receber_sinal)
    signal.signal(signal.SIGTERM, ao_receber_sinal)
    if hasattr(signal, "SIGBREAK"):  # Windows: Ctrl+Break / fechamento do console
        signal.signal(signal.SIGBREAK, ao_receber_sinal)

    while not parada_pedida.is_set():
        app = CameratonaApp(headless=headless)
        try:
            app.iniciar()
            break  # saiu normalmente (Q na janela ou sinal de parada)
        except Exception as e:
            if not headless:
                raise
            # Modo serviço: registra e reinicia sozinho
            logger.exception(f"Erro inesperado: {e}. Reiniciando em {RESTART_DELAY_S}s...")
            parada_pedida.wait(RESTART_DELAY_S)


if __name__ == "__main__":
    main()
