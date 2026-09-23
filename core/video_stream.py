import av
import numpy as np
import threading
import time

class VideoStream:
    def __init__(self, rtsp_url):
        self.rtsp_url = rtsp_url
        self.running = False
        self.frame = None
        self.lock = threading.Lock()
        
        # Opções avançadas do FFmpeg injetadas diretamente no container
        options = {
            'rtsp_transport': 'udp',     # Força o UDP, já sabemos que a câmera aceita
            'flags': 'low_delay',        # Otimiza para tempo real (sem buffer de atraso)
            'stimeout': '5000000',       # Timeout de 5 segundos em microssegundos
            'max_delay': '500000'        # Limite de atraso tolerável
        }
        
        print("Iniciando negociação PyAV com a câmera...")
        self.container = av.open(self.rtsp_url, options=options)
        self.video_stream = self.container.streams.video[0]
        self.video_stream.thread_type = 'AUTO' # Habilita decodificação multi-thread
        
    def start(self):
        self.running = True
        self.thread = threading.Thread(target=self._update, daemon=True)
        self.thread.start()
        return self
        
    def _update(self):
        try:
            # O demux continua puxando os pacotes da rede
            for packet in self.container.demux(self.video_stream):
                if not self.running:
                    break
                
                if packet.dts is None:
                    continue
                    
                # Isolamento de falhas: tenta decodificar apenas o pacote atual
                try:
                    for av_frame in packet.decode():
                        img = av_frame.to_ndarray(format='bgr24')
                        
                        with self.lock:
                            self.frame = img
                except Exception:
                    # Se o frame chegou corrompido (perda de pacotes UDP),
                    # ignoramos silenciosamente e tentamos ler o próximo.
                    continue
                        
        except Exception as e:
            print(f"\n[Aviso de Rede] A conexão sofreu interrupção fatal: {e}")
        finally:
            self.running = False
    
    def read(self):
        with self.lock:
            if self.frame is not None:
                # Retorna o frame copiado para evitar que o PyAV sobrescreva a memória durante o YOLO
                return True, self.frame.copy()
            return False, None
            
    def stop(self):
        self.running = False
        if hasattr(self, 'thread'):
            self.thread.join(timeout=2.0)
        if hasattr(self, 'container'):
            self.container.close()