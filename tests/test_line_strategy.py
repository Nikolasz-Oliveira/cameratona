"""
Testes da LineStrategy (não precisam de câmera nem de GPU).

Rodar a partir da raiz do projeto:
    python -m unittest discover tests
"""
import unittest
from unittest.mock import patch

from core.analytics.line_strategy import LineStrategy


def det(track_id, x, y):
    return {"id": track_id, "bbox": (x - 10, y - 40, x + 10, y), "foot_point": (x, y)}


class LineStrategyTest(unittest.TestCase):
    def setUp(self):
        self.s = LineStrategy()
        # Linha horizontal de (100,100) a (200,100); lado +1 = y > 100 (abaixo, na imagem)
        self.s.set_geometry([[100, 100], [200, 100]])
        self.s.inverted = False
        self.s.cooldown_s = 0
        self.s.segment_margin = 0
        self.s.handover_dist = 80

    def feed(self, *frames):
        for frame in frames:
            self.s.update(frame)

    def test_travessia_simples_conta_entrada_e_saida(self):
        self.feed([det(1, 150, 80)], [det(1, 150, 120)])
        self.assertEqual(self.s.get_stats(), (1, 0))
        self.feed([det(1, 150, 80)])
        self.assertEqual(self.s.get_stats(), (1, 1))

    def test_contornar_a_ponta_nao_conta(self):
        # Passa por fora do segmento (x=250), troca de lado lá, e volta para dentro
        self.feed([det(1, 150, 80)], [det(1, 250, 80)], [det(1, 250, 120)], [det(1, 150, 120)])
        self.assertEqual(self.s.get_stats(), (0, 0))

    def test_linha_vertical(self):
        self.s.set_geometry([[100, 100], [100, 300]])
        self.feed([det(1, 80, 200)], [det(1, 120, 200)])
        self.assertEqual(sum(self.s.get_stats()), 1)
        # Fora da altura do segmento não conta
        self.feed([det(2, 80, 500)], [det(2, 120, 500)])
        self.assertEqual(sum(self.s.get_stats()), 1)

    def test_redesenhar_linha_nao_gera_contagem_falsa(self):
        self.feed([det(1, 150, 80)])
        self.s.set_geometry([[100, 50], [200, 50]])  # pessoa agora está do outro lado
        self.feed([det(1, 150, 81)])
        self.assertEqual(self.s.get_stats(), (0, 0))

    def test_inverter_direcao(self):
        self.s.toggle_direction()
        self.feed([det(1, 150, 80)], [det(1, 150, 120)])
        self.assertEqual(self.s.get_stats(), (0, 1))

    def test_seta_aponta_para_o_lado_de_entrada(self):
        (_, sy), (_, ey) = self.s.get_entry_arrow()
        self.assertGreater(ey, sy)  # entrada = descer na imagem (y maior)
        self.s.toggle_direction()
        (_, sy), (_, ey) = self.s.get_entry_arrow()
        self.assertLess(ey, sy)

    def test_troca_de_id_nao_conta_duas_vezes(self):
        self.feed([det(1, 150, 80)], [det(1, 150, 120)])   # ID 1 entra
        self.feed([], [])                                   # tracker perde a pessoa
        self.feed([det(7, 155, 95)], [det(7, 150, 80)], [det(7, 150, 120)])  # volta como ID 7
        # ID 7 herdou o estado (DENTRO): a saída conta, a 2a entrada é a única nova contagem
        self.assertEqual(self.s.get_stats(), (2, 1))
        self.feed([], [])
        self.feed([det(9, 150, 125)], [det(9, 150, 80)], [det(9, 150, 120)])
        self.assertEqual(self.s.get_stats(), (3, 2))

    def test_troca_de_id_no_meio_da_travessia_ainda_conta(self):
        self.feed([det(1, 150, 80)])            # ID 1 antes da linha
        self.feed([])                            # tracker perde a pessoa sobre a linha
        self.feed([det(2, 150, 120)])            # reaparece do outro lado como ID 2
        self.assertEqual(self.s.get_stats(), (1, 0))

    def test_cooldown_herdado_na_troca_de_id(self):
        self.s.cooldown_s = 3.0
        with patch("core.analytics.line_strategy._now", side_effect=[0, 1, 1.2, 1.5, 2]):
            self.feed([det(1, 150, 99)], [det(1, 150, 101)])  # entra (t=1)
            self.feed([])
            self.feed([det(2, 150, 99)], [det(2, 150, 101)])  # novo ID tremendo na linha
        self.assertEqual(self.s.get_stats(), (1, 0))

    def test_cooldown_ignora_tremida_na_linha(self):
        self.s.cooldown_s = 3.0
        with patch("core.analytics.line_strategy._now", side_effect=[0, 1, 1.5, 2, 10, 11]):
            self.feed([det(1, 150, 99)], [det(1, 150, 101)],   # entra (t=1)
                      [det(1, 150, 99)], [det(1, 150, 101)],   # tremida dentro do cooldown
                      [det(1, 150, 80)])                       # sai de verdade (t=10)
        self.assertEqual(self.s.get_stats(), (1, 1))

    def test_ids_distantes_nao_herdam_estado(self):
        self.feed([det(1, 150, 80)], [det(1, 150, 120)])
        self.feed([])
        self.feed([det(2, 600, 600)])
        self.assertIn(1, self.s.track_history)  # ID 1 continua aguardando, não foi herdado


if __name__ == "__main__":
    unittest.main()
