"""
Envio de dados para o ThingsBoard via MQTT (API de dispositivo).

- Autenticação por Access Token do device (vai como "username" da conexão MQTT).
- Telemetria: tópico v1/devices/me/telemetry, no formato {"ts": <ms>, "values": {...}},
  para que dados enviados com atraso mantenham o horário em que aconteceram.
- Atributos:  tópico v1/devices/me/attributes.
- Tudo roda em threads próprias: rede lenta ou fora do ar nunca trava o vídeo.
- Se a conexão cair, as mensagens ficam numa fila em memória (limitada) e são
  enviadas quando o ThingsBoard voltar.
"""
import json
import threading
import time
from collections import deque

from config.config_loader import Config
from utils.logger import logger

TELEMETRY_TOPIC = "v1/devices/me/telemetry"
ATTRIBUTES_TOPIC = "v1/devices/me/attributes"


def _now_ms():
    return int(time.time() * 1000)


class ThingsBoardClient:
    def __init__(self, host, port, access_token, client_id="cameratona",
                 queue_max=10000, publish_timeout_s=5.0):
        self.host = host
        self.port = int(port)
        self.access_token = access_token
        self.client_id = client_id
        self.publish_timeout_s = float(publish_timeout_s)

        self._queue = deque(maxlen=int(queue_max))   # cheia: descarta a mais antiga
        self._cond = threading.Condition()
        self._connected = threading.Event()
        self._running = False
        self._worker = None
        self._client = None
        self._dropped_warned = False

    # ------------------------------------------------------------------ ciclo de vida
    def start(self):
        import paho.mqtt.client as mqtt

        try:  # paho-mqtt 2.x
            client = mqtt.Client(callback_api_version=mqtt.CallbackAPIVersion.VERSION2,
                                 client_id=self.client_id)
        except AttributeError:  # paho-mqtt 1.x
            client = mqtt.Client(client_id=self.client_id)

        client.username_pw_set(self.access_token)
        client.on_connect = self._on_connect
        client.on_disconnect = self._on_disconnect
        client.reconnect_delay_set(min_delay=1, max_delay=30)
        self._client = client

        logger.info(f"ThingsBoard: conectando em {self.host}:{self.port}...")
        client.connect_async(self.host, self.port, keepalive=60)
        client.loop_start()  # thread do paho: conecta e reconecta sozinho

        self._running = True
        self._worker = threading.Thread(target=self._publish_loop, daemon=True)
        self._worker.start()
        return self

    def stop(self, flush_timeout_s=3.0):
        """Tenta enviar o que estiver na fila por alguns segundos e desconecta."""
        deadline = time.monotonic() + flush_timeout_s
        while self._queue and self._connected.is_set() and time.monotonic() < deadline:
            time.sleep(0.05)
        if self._queue:
            logger.warning(f"ThingsBoard: {len(self._queue)} mensagens não enviadas ao encerrar.")

        self._running = False
        with self._cond:
            self._cond.notify_all()
        if self._worker:
            self._worker.join(timeout=self.publish_timeout_s + 1)
        if self._client:
            try:
                self._client.disconnect()
                self._client.loop_stop()
            except Exception:
                pass

    @property
    def connected(self):
        return self._connected.is_set()

    # ------------------------------------------------------------------ API pública
    def send_telemetry(self, values, ts_ms=None):
        payload = {"ts": ts_ms if ts_ms is not None else _now_ms(), "values": values}
        self._enqueue(TELEMETRY_TOPIC, payload)

    def send_attributes(self, attributes):
        self._enqueue(ATTRIBUTES_TOPIC, attributes)

    # ------------------------------------------------------------------ interno
    def _enqueue(self, topic, payload):
        with self._cond:
            if len(self._queue) == self._queue.maxlen and not self._dropped_warned:
                logger.warning("ThingsBoard: fila cheia, descartando mensagens mais antigas.")
                self._dropped_warned = True
            self._queue.append((topic, json.dumps(payload, ensure_ascii=False)))
            self._cond.notify()

    def _on_connect(self, client, userdata, flags, reason_code, properties=None):
        failed = getattr(reason_code, "is_failure", None)
        if failed is None:
            failed = reason_code != 0
        if failed:
            # Código 4/5 (ou "Bad user name or password"/"Not authorized") = token errado
            logger.error(f"ThingsBoard recusou a conexão: {reason_code}. Verifique o access_token.")
            return
        logger.info("ThingsBoard: conectado.")
        self._connected.set()
        with self._cond:
            self._cond.notify_all()

    def _on_disconnect(self, client, userdata, *args):
        if self._connected.is_set():
            logger.warning("ThingsBoard: conexão perdida. Guardando dados até reconectar.")
        self._connected.clear()

    def _publish_loop(self):
        while self._running:
            with self._cond:
                while self._running and (not self._queue or not self._connected.is_set()):
                    self._cond.wait(timeout=1.0)
                if not self._running:
                    return
                topic, payload = self._queue[0]

            if self._publish(topic, payload):
                with self._cond:
                    # Remove só depois de confirmado (QoS 1)
                    if self._queue and self._queue[0] == (topic, payload):
                        self._queue.popleft()
                    self._dropped_warned = False
            else:
                time.sleep(1.0)

    def _publish(self, topic, payload):
        try:
            info = self._client.publish(topic, payload, qos=1)
            info.wait_for_publish(timeout=self.publish_timeout_s)
            return info.is_published()
        except Exception as e:
            logger.debug(f"ThingsBoard: falha ao publicar ({e}).")
            return False


class NullThingsBoardClient:
    """Usado quando a integração está desligada ou sem token: ignora tudo."""
    connected = False

    def start(self):
        return self

    def stop(self, *args, **kwargs):
        pass

    def send_telemetry(self, *args, **kwargs):
        pass

    def send_attributes(self, *args, **kwargs):
        pass


def create_thingsboard_client():
    cfg = Config.thingsboard
    if not cfg.get("enabled", True):
        logger.info("ThingsBoard: integração desativada (thingsboard.enabled=false).")
        return NullThingsBoardClient()

    token = cfg.get("access_token", "")
    if not token:
        logger.warning("ThingsBoard: sem access_token (defina no settings.local.json ou "
                       "CAMERATONA_TB_TOKEN). Os dados não serão enviados.")
        return NullThingsBoardClient()

    try:
        import paho.mqtt.client  # noqa: F401
    except ImportError:
        logger.error("ThingsBoard: pacote 'paho-mqtt' não instalado (pip install -r requirements.txt).")
        return NullThingsBoardClient()

    return ThingsBoardClient(
        host=cfg.get("host", "thingsboard.labiot"),
        port=cfg.get("port", 1883),
        access_token=token,
        client_id=cfg.get("client_id", "cameratona"),
        queue_max=cfg.get("queue_max", 10000),
    )
