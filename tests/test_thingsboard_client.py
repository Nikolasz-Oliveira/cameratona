"""
Testes do cliente ThingsBoard com um broker MQTT simulado (não precisa de rede).

    python -m unittest discover tests
"""
import json
import sys
import threading
import time
import types
import unittest
from unittest.mock import patch


# ---------------------------------------------------------------- paho-mqtt simulado
class _FakeInfo:
    def __init__(self, ok):
        self._ok = ok

    def wait_for_publish(self, timeout=None):
        if not self._ok:
            raise RuntimeError("not connected")

    def is_published(self):
        return self._ok


class _FakeClient:
    instances = []

    def __init__(self, callback_api_version=None, client_id=""):
        self.username = None
        self.online = False
        self.published = []
        self.on_connect = None
        self.on_disconnect = None
        _FakeClient.instances.append(self)

    def username_pw_set(self, username, password=None):
        self.username = username

    def reconnect_delay_set(self, min_delay, max_delay):
        pass

    def connect_async(self, host, port, keepalive=60):
        self.host, self.port = host, port

    def loop_start(self):
        pass

    def loop_stop(self):
        pass

    def disconnect(self):
        pass

    def publish(self, topic, payload, qos=0):
        if self.online:
            self.published.append((topic, json.loads(payload)))
        return _FakeInfo(self.online)

    # helpers do teste
    def simulate_connect(self, rc=0):
        self.online = rc == 0
        self.on_connect(self, None, {}, rc, None)

    def simulate_disconnect(self):
        self.online = False
        self.on_disconnect(self, None, {}, 7, None)


_client_mod = types.SimpleNamespace(
    Client=_FakeClient,
    CallbackAPIVersion=types.SimpleNamespace(VERSION2=2),
)
_fake_paho = types.ModuleType("paho")
_fake_mqtt = types.ModuleType("paho.mqtt")
_fake_mqtt.client = _client_mod
_fake_paho.mqtt = _fake_mqtt
sys.modules.setdefault("paho", _fake_paho)
sys.modules.setdefault("paho.mqtt", _fake_mqtt)
sys.modules.setdefault("paho.mqtt.client", _client_mod)

from core.integrations import thingsboard_client as tbmod  # noqa: E402
from core.analytics.line_strategy import LineStrategy  # noqa: E402


def wait_until(cond, timeout=3.0):
    end = time.monotonic() + timeout
    while time.monotonic() < end:
        if cond():
            return True
        time.sleep(0.01)
    return False


class ThingsBoardClientTest(unittest.TestCase):
    def setUp(self):
        _FakeClient.instances.clear()
        self.tb = tbmod.ThingsBoardClient("thingsboard.labiot", 1883, "TOKEN123",
                                          publish_timeout_s=0.1).start()
        self.mqtt = _FakeClient.instances[-1]

    def tearDown(self):
        self.tb.stop(flush_timeout_s=0)

    def test_usa_token_como_usuario(self):
        self.assertEqual(self.mqtt.username, "TOKEN123")
        self.assertEqual((self.mqtt.host, self.mqtt.port), ("thingsboard.labiot", 1883))

    def test_formato_da_telemetria_com_timestamp(self):
        self.mqtt.simulate_connect()
        self.tb.send_telemetry({"evento": "ENTRADA", "entradas": 1}, ts_ms=1700000000000)
        self.assertTrue(wait_until(lambda: self.mqtt.published))
        topic, payload = self.mqtt.published[0]
        self.assertEqual(topic, "v1/devices/me/telemetry")
        self.assertEqual(payload, {"ts": 1700000000000, "values": {"evento": "ENTRADA", "entradas": 1}})

    def test_atributos(self):
        self.mqtt.simulate_connect()
        self.tb.send_attributes({"camera_ip": "1.2.3.4"})
        self.assertTrue(wait_until(lambda: self.mqtt.published))
        self.assertEqual(self.mqtt.published[0], ("v1/devices/me/attributes", {"camera_ip": "1.2.3.4"}))

    def test_guarda_offline_e_envia_em_ordem_ao_reconectar(self):
        self.mqtt.simulate_connect()
        self.mqtt.simulate_disconnect()
        for i in range(5):
            self.tb.send_telemetry({"n": i}, ts_ms=i)
        time.sleep(0.2)
        self.assertEqual(self.mqtt.published, [])
        self.mqtt.simulate_connect()
        self.assertTrue(wait_until(lambda: len(self.mqtt.published) == 5))
        self.assertEqual([p["values"]["n"] for _, p in self.mqtt.published], [0, 1, 2, 3, 4])

    def test_token_errado_nao_marca_como_conectado(self):
        with self.assertLogs("cameratona", level="ERROR"):
            self.mqtt.simulate_connect(rc=5)
        self.assertFalse(self.tb.connected)

    def test_fila_limitada_descarta_as_mais_antigas(self):
        self.tb._queue = type(self.tb._queue)(maxlen=3)
        for i in range(5):
            self.tb.send_telemetry({"n": i}, ts_ms=i)
        self.mqtt.simulate_connect()
        self.assertTrue(wait_until(lambda: len(self.mqtt.published) == 3))
        self.assertEqual([p["values"]["n"] for _, p in self.mqtt.published], [2, 3, 4])


class FactoryTest(unittest.TestCase):
    def test_sem_token_usa_cliente_nulo(self):
        with patch.object(tbmod.Config, "_config", {"thingsboard": {"access_token": ""}}):
            client = tbmod.create_thingsboard_client()
        self.assertIsInstance(client, tbmod.NullThingsBoardClient)
        client.start().send_telemetry({"x": 1})  # não faz nada, não quebra

    def test_desativado(self):
        with patch.object(tbmod.Config, "_config", {"thingsboard": {"enabled": False, "access_token": "T"}}):
            self.assertIsInstance(tbmod.create_thingsboard_client(), tbmod.NullThingsBoardClient)

    def test_com_token_cria_cliente_real(self):
        with patch.object(tbmod.Config, "_config", {"thingsboard": {"access_token": "T"}}):
            self.assertIsInstance(tbmod.create_thingsboard_client(), tbmod.ThingsBoardClient)


class EventosDaEstrategiaTest(unittest.TestCase):
    def test_entrada_e_saida_geram_eventos(self):
        s = LineStrategy()
        s.set_geometry([[100, 100], [200, 100]])
        s.inverted, s.cooldown_s, s.segment_margin = False, 0, 0
        eventos = []
        s.add_listener(eventos.append)
        det = lambda y: [{"id": 1, "bbox": (0, 0, 1, 1), "foot_point": (150, y)}]
        for y in (80, 120, 80):
            s.update(det(y))
        self.assertEqual([e["evento"] for e in eventos], ["ENTRADA", "SAIDA"])
        self.assertEqual((eventos[1]["entradas"], eventos[1]["saidas"]), (1, 1))
        self.assertIn("permanencia_s", eventos[1])

    def test_listener_com_erro_nao_derruba_a_contagem(self):
        s = LineStrategy()
        s.set_geometry([[100, 100], [200, 100]])
        s.inverted, s.cooldown_s, s.segment_margin = False, 0, 0

        def quebra(_):
            raise ValueError("falhou")
        s.add_listener(quebra)
        with self.assertLogs("cameratona", level="ERROR"):
            for y in (80, 120):
                s.update([{"id": 1, "bbox": (0, 0, 1, 1), "foot_point": (150, y)}])
        self.assertEqual(s.get_stats(), (1, 0))


if __name__ == "__main__":
    unittest.main()
