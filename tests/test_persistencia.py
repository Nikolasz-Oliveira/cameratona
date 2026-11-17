"""
Testes dos totais persistentes, totais do dia e gravação da linha no settings.local.json.

    python -m unittest discover tests
"""
import json
import tempfile
import unittest
from datetime import date
from pathlib import Path
from unittest.mock import patch

from config.config_loader import ConfigLoader
from core.analytics.line_strategy import LineStrategy
from core.state.state_store import StateStore


def det(track_id, x, y):
    return {"id": track_id, "bbox": (0, 0, 1, 1), "foot_point": (x, y)}


def nova_estrategia():
    s = LineStrategy()
    s.set_geometry([[100, 100], [200, 100]])
    s.inverted, s.cooldown_s, s.segment_margin = False, 0, 0
    return s


def atravessar(s, track_id=1, vezes=1):
    ys = [80] + [120, 80] * vezes
    for y in ys:
        s.update([det(track_id, 150, y)])


class _FakeDate(date):
    hoje = date(2026, 11, 17)

    @classmethod
    def today(cls):
        return cls.hoje


class StateStoreTest(unittest.TestCase):
    def setUp(self):
        self.dir = tempfile.TemporaryDirectory()
        self.path = Path(self.dir.name) / "data" / "estado.json"

    def tearDown(self):
        self.dir.cleanup()

    def test_sem_arquivo_comeca_vazio(self):
        self.assertEqual(StateStore(self.path).load(), {})

    def test_salva_e_carrega(self):
        StateStore(self.path).save({"entradas": 5})
        self.assertEqual(StateStore(self.path).load(), {"entradas": 5})
        self.assertFalse(self.path.with_suffix(".tmp").exists())

    def test_arquivo_corrompido_vira_backup(self):
        self.path.parent.mkdir(parents=True)
        self.path.write_text("{ quebrado")
        with self.assertLogs("cameratona", level="ERROR"):
            self.assertEqual(StateStore(self.path).load(), {})
        self.assertTrue(self.path.with_suffix(".corrompido.json").exists())


class TotaisPersistentesTest(unittest.TestCase):
    def test_totais_continuam_apos_reinicio(self):
        with tempfile.TemporaryDirectory() as d:
            store = StateStore(Path(d) / "estado.json")

            s1 = nova_estrategia()
            atravessar(s1, vezes=2)                  # 2 entradas, 2 saídas
            store.save(s1.export_state())

            s2 = nova_estrategia()                   # "reiniciou o programa"
            s2.restore_state(store.load())
            self.assertEqual(s2.get_stats(), (2, 2))
            atravessar(s2, track_id=5)
            self.assertEqual(s2.get_stats(), (3, 3))
            self.assertEqual(s2.get_daily_stats(), (3, 3))

    def test_eventos_levam_totais_do_dia(self):
        s = nova_estrategia()
        eventos = []
        s.add_listener(eventos.append)
        atravessar(s)
        self.assertEqual(eventos[-1]["entradas_hoje"], 1)
        self.assertEqual(eventos[-1]["saidas_hoje"], 1)


@patch("core.analytics.line_strategy.date", _FakeDate)
class TotaisDoDiaTest(unittest.TestCase):
    def setUp(self):
        _FakeDate.hoje = date(2026, 11, 17)

    def test_virada_do_dia_zera_so_os_totais_do_dia(self):
        s = nova_estrategia()
        atravessar(s, vezes=2)
        _FakeDate.hoje = date(2026, 11, 18)
        self.assertEqual(s.get_daily_stats(), (0, 0))
        self.assertEqual(s.get_stats(), (2, 2))
        atravessar(s, track_id=9)
        self.assertEqual(s.get_daily_stats(), (1, 1))
        self.assertEqual(s.get_stats(), (3, 3))

    def test_estado_de_ontem_restaura_total_mas_zera_o_dia(self):
        s = nova_estrategia()
        s.restore_state({"entradas": 10, "saidas": 8, "dia": "2026-11-16",
                         "entradas_hoje": 4, "saidas_hoje": 3})
        self.assertEqual(s.get_stats(), (10, 8))
        self.assertEqual(s.get_daily_stats(), (0, 0))

    def test_estado_de_hoje_restaura_o_dia(self):
        s = nova_estrategia()
        s.restore_state({"entradas": 10, "saidas": 8, "dia": "2026-11-17",
                         "entradas_hoje": 4, "saidas_hoje": 3})
        self.assertEqual(s.get_daily_stats(), (4, 3))


class SaveLocalTest(unittest.TestCase):
    def test_grava_linha_sem_apagar_o_token(self):
        with tempfile.TemporaryDirectory() as d:
            base = Path(d) / "settings.json"
            local = Path(d) / "settings.local.json"
            base.write_text(json.dumps({"analytics": {"geometry": {"line_p1": [1, 1], "line_p2": [2, 2]}}}))
            local.write_text(json.dumps({"thingsboard": {"access_token": "TOKEN"}}))

            cfg = ConfigLoader(base, local)
            cfg.save_local({"analytics": {"geometry": {"line_p1": [10, 10], "line_p2": [20, 20]}}})

            salvo = json.loads(local.read_text())
            self.assertEqual(salvo["thingsboard"]["access_token"], "TOKEN")
            self.assertEqual(salvo["analytics"]["geometry"]["line_p1"], [10, 10])
            # E vale ao recarregar
            self.assertEqual(ConfigLoader(base, local).analytics["geometry"]["line_p2"], [20, 20])
            self.assertEqual(cfg.analytics["geometry"]["line_p1"], [10, 10])


if __name__ == "__main__":
    unittest.main()
