import threading
import time

import av

from config.config_loader import Config
from utils.logger import logger


class RTSPStream:
    """
    Lê a câmera em uma thread separada, mantendo apenas o frame mais recente.

    - Reconecta automaticamente se a conexão cair (ou se a câmera não estiver
      disponível ao iniciar).
    - read() só devolve um frame NOVO; se nenhum frame chegou desde a última
      leitura, devolve (False, None). Assim a IA não reprocessa uma imagem
      congelada quando a câmera para de enviar dados.
    """

    def __init__(self):
        cam = Config.camera
        self.rtsp_url = Config.get_rtsp_url()
        self.safe_url = Config.get_rtsp_url_safe()
        self.timeout_s = float(cam.get("timeout_s", 5))
        self.reconnect_delay_s = float(cam.get("reconnect_delay_s", 3))

        # 'udp' é o padrão: câmeras tipo Yoosee (caminho onvif1/onvif2) só aceitam UDP.
        # Em câmeras que suportam, 'tcp' é mais estável (sem perda de pacotes).
        self.options = {
            "rtsp_transport": cam.get("transport", "udp"),
            "fflags": "nobuffer",
            "flags": "low_delay",
            "max_delay": "500000",
            # Em FFmpeg >= 5 a opção se chama 'timeout' (antes era 'stimeout'), em microssegundos
            "timeout": str(int(self.timeout_s * 1_000_000)),
        }

        self.running = False
        self.connected = False
        self.thread = None
        self.container = None

        self.lock = threading.Lock()
        self.frame = None
        self.frame_id = 0
        self.last_read_id = 0
        self.last_frame_time = None

    # ------------------------------------------------------------------ ciclo de vida
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()
        return self

    def stop(self):
        self.running = False
        if self.thread:
            self.thread.join(timeout=self.timeout_s + 1)
        self._close_container()

    # ------------------------------------------------------------------ leitura
    def read(self):
        """Retorna (True, frame) se chegou um frame novo desde a última chamada."""
        with self.lock:
            if self.frame is not None and self.frame_id != self.last_read_id:
                self.last_read_id = self.frame_id
                return True, self.frame.copy()
            return False, None

    def seconds_since_last_frame(self):
        """Tempo desde o último frame recebido (None se nunca recebeu)."""
        with self.lock:
            if self.last_frame_time is None:
                return None
            return time.monotonic() - self.last_frame_time

    # ------------------------------------------------------------------ interno
    def _connect(self):
        logger.info(f"Tentando conectar ao stream: {self.safe_url}")
        self.container = av.open(
            self.rtsp_url,
            options=self.options,
            timeout=(self.timeout_s, self.timeout_s),
        )
        video_stream = self.container.streams.video[0]
        video_stream.thread_type = "AUTO"
        self.connected = True
        logger.info("Conexão estabelecida com sucesso.")
        return video_stream

    def _close_container(self):
        container, self.container = self.container, None
        if container is not None:
            try:
                container.close()
            except Exception:
                pass

    def _run(self):
        while self.running:
            try:
                video_stream = self._connect()
                for packet in self.container.demux(video_stream):
                    if not self.running:
                        break
                    if packet.dts is None:
                        continue
                    try:
                        for av_frame in packet.decode():
                            img = av_frame.to_ndarray(format="bgr24")
                            with self.lock:
                                self.frame = img
                                self.frame_id += 1
                                self.last_frame_time = time.monotonic()
                    except Exception:
                        # Pacote corrompido: descarta e segue
                        continue
                else:
                    if self.running:
                        logger.warning("Stream encerrado pela câmera.")
            except Exception as e:
                if self.running:
                    logger.error(f"Falha na conexão com a câmera: {e}")
            finally:
                self.connected = False
                self._close_container()

            if self.running:
                logger.info(f"Reconectando em {self.reconnect_delay_s:.0f}s...")
                time.sleep(self.reconnect_delay_s)
