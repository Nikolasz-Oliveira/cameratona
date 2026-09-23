import av
import threading
import time
from config.config_loader import Config
from utils.logger import logger

class RTSPStream:
    def __init__(self):
        self.rtsp_url = Config.get_rtsp_url()
        self.running = False
        self.frame = None
        self.lock = threading.Lock()
        
        options = {
            'rtsp_transport': 'udp',
            'flags': 'low_delay',
            'stimeout': '5000000',
            'max_delay': '500000'
        }
        
        logger.info(f"Tentando conectar ao stream: {self.rtsp_url}")
        self.container = av.open(self.rtsp_url, options=options)
        self.video_stream = self.container.streams.video[0]
        self.video_stream.thread_type = 'AUTO'
        logger.info("Conexão estabelecida com sucesso.")
        
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()
        return self
        
    def _update(self):
        try:
            for packet in self.container.demux(self.video_stream):
                if not self.running:
                    break
                
                if packet.dts is None:
                    continue
                    
                try:
                    for av_frame in packet.decode():
                        img = av_frame.to_ndarray(format='bgr24')
                        with self.lock:
                            self.frame = img
                except Exception:
                    continue
                        
        except Exception as e:
            logger.error(f"Interrupção na conexão de rede: {e}")
        finally:
            self.running = False
    
    def read(self):
        with self.lock:
            if self.frame is not None:
                return True, self.frame.copy()
            return False, None
            
    def stop(self):
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=2.0)
        if hasattr(self, 'container'):
            self.container.close()