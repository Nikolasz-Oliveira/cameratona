import math
import time
from datetime import date

from core.analytics.strategy_interface import AnalyticsStrategy
from config.config_loader import Config
from utils.logger import logger


def _cross(o, a, b):
    """Produto vetorial 2D de (a - o) x (b - o). Sinal indica o lado de b em relação a o->a."""
    return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])


def _now():
    """Relógio usado nos eventos (isolado para facilitar testes)."""
    return time.time()


def _sign(v):
    return 1 if v > 0 else -1 if v < 0 else 0


class LineStrategy(AnalyticsStrategy):
    """
    Conta entradas e saídas quando o "ponto do pé" de uma pessoa ATRAVESSA o
    segmento de linha (e não apenas quando muda de lado da reta infinita).

    Convenção de direção: ENTRADA = movimento para o lado indicado pela seta
    desenhada na tela. Use 'invert_direction' no settings.json (ou a tecla I)
    para inverter.
    """

    def __init__(self):
        cfg = Config.analytics
        geom = cfg.get("geometry", {})
        self.p1 = tuple(geom.get("line_p1", [730, 400]))
        self.p2 = tuple(geom.get("line_p2", [850, 400]))

        self.inverted = bool(cfg.get("invert_direction", False))
        self.cooldown_s = float(cfg.get("cooldown_s", 3.0))
        self.max_lost_frames = int(cfg.get("max_lost_frames", 30))
        self.segment_margin = float(cfg.get("segment_margin_px", 20))
        self.handover_dist = float(cfg.get("id_handover_max_dist_px", 80))

        # Totais desde a instalação (persistidos em data/estado.json pelo main)
        self.entradas = 0
        self.saidas = 0
        # Totais do dia (zeram à meia-noite, horário local)
        self.dia = date.today().isoformat()
        self.entradas_hoje = 0
        self.saidas_hoje = 0
        # track_id -> {"last_point", "last_side", "logical_state",
        #              "last_event_time", "entry_time", "lost_frames"}
        self.track_history = {}

    # ------------------------------------------------------------------ API pública
    def get_geometry(self):
        return [self.p1, self.p2]

    def get_stats(self):
        return self.entradas, self.saidas

    def get_daily_stats(self):
        self._roll_day()
        return self.entradas_hoje, self.saidas_hoje

    def export_state(self):
        self._roll_day()
        return {
            "entradas": self.entradas,
            "saidas": self.saidas,
            "dia": self.dia,
            "entradas_hoje": self.entradas_hoje,
            "saidas_hoje": self.saidas_hoje,
        }

    def restore_state(self, state):
        if not state:
            return
        self.entradas = int(state.get("entradas", 0))
        self.saidas = int(state.get("saidas", 0))
        self.dia = state.get("dia", self.dia)
        self.entradas_hoje = int(state.get("entradas_hoje", 0))
        self.saidas_hoje = int(state.get("saidas_hoje", 0))
        self._roll_day()  # se o estado é de outro dia, zera os totais do dia
        logger.info(f"Totais restaurados: entradas={self.entradas}, saidas={self.saidas} "
                    f"(hoje: {self.entradas_hoje}/{self.saidas_hoje}).")

    def set_geometry(self, points):
        if len(points) >= 2:
            self.p1 = tuple(points[0])
            self.p2 = tuple(points[1])
            # O histórico de lados foi calculado em relação à linha antiga;
            # reaproveitá-lo geraria contagens falsas.
            self.track_history.clear()
            logger.info(f"Geometria da Linha atualizada para: {self.p1} -> {self.p2}")

    def toggle_direction(self):
        self.inverted = not self.inverted
        self.track_history.clear()
        logger.info(f"Direção de entrada invertida (invert_direction={self.inverted}).")

    def get_entry_arrow(self, length=40):
        """Seta (início, fim) a partir do meio da linha apontando para o lado de ENTRADA."""
        mx = (self.p1[0] + self.p2[0]) / 2
        my = (self.p1[1] + self.p2[1]) / 2
        dx = self.p2[0] - self.p1[0]
        dy = self.p2[1] - self.p1[1]
        norm = math.hypot(dx, dy) or 1.0
        # Normal (-dy, dx) aponta para o lado onde _cross(p1, p2, ponto) > 0 (lado +1)
        nx, ny = -dy / norm, dx / norm
        if self.inverted:
            nx, ny = -nx, -ny
        return (int(mx), int(my)), (int(mx + nx * length), int(my + ny * length))

    def update(self, detections):
        now = _now()
        self._roll_day()
        current_ids = set()

        for det in detections:
            track_id = det["id"]
            point = det["foot_point"]
            current_ids.add(track_id)

            side = self._side_of_line(point)

            if track_id not in self.track_history:
                inherited = self._take_over_lost_track(point, current_ids)
                if inherited is not None:
                    self.track_history[track_id] = inherited
                else:
                    self.track_history[track_id] = {
                        "last_point": None, "last_side": 0,
                        "logical_state": "DESCONHECIDO",
                        "last_event_time": None, "entry_time": None,
                        "lost_frames": 0,
                    }

            history = self.track_history[track_id]
            history["lost_frames"] = 0

            # Ponto exatamente sobre a reta: espera o próximo frame para decidir
            if side == 0:
                continue

            prev_point = history["last_point"]
            prev_side = history["last_side"]

            if prev_point is not None and prev_side != side \
                    and self._crosses_segment(prev_point, point):
                self._register_crossing(track_id, history, prev_side, side, now)

            # Sempre atualiza a posição, inclusive fora do segmento: assim quem
            # contorna a ponta da linha não é contado ao voltar.
            history["last_point"] = point
            history["last_side"] = side

        self._age_lost_tracks(current_ids)

    # ------------------------------------------------------------------ interno
    def _roll_day(self):
        hoje = date.today().isoformat()
        if hoje != self.dia:
            logger.info(f"Novo dia ({hoje}). Totais de {self.dia}: "
                        f"entradas={self.entradas_hoje}, saidas={self.saidas_hoje}.")
            self.dia = hoje
            self.entradas_hoje = 0
            self.saidas_hoje = 0

    def _counts(self):
        return {"entradas": self.entradas, "saidas": self.saidas,
                "entradas_hoje": self.entradas_hoje, "saidas_hoje": self.saidas_hoje}

    def _side_of_line(self, point):
        s = _sign(_cross(self.p1, self.p2, point))
        return -s if self.inverted else s

    def _extended_segment(self):
        """Segmento da linha estendido em 'segment_margin' px em cada ponta (tolerância)."""
        dx = self.p2[0] - self.p1[0]
        dy = self.p2[1] - self.p1[1]
        norm = math.hypot(dx, dy) or 1.0
        ux, uy = dx / norm * self.segment_margin, dy / norm * self.segment_margin
        return (self.p1[0] - ux, self.p1[1] - uy), (self.p2[0] + ux, self.p2[1] + uy)

    def _crosses_segment(self, a, b):
        """O deslocamento a->b cruza o segmento da linha (com margem)?"""
        q1, q2 = self._extended_segment()
        # a e b já estão em lados opostos da reta (verificado antes); falta saber
        # se a interseção cai DENTRO do segmento, i.e. q1 e q2 em lados opostos de a->b.
        d1 = _cross(a, b, q1)
        d2 = _cross(a, b, q2)
        return d1 * d2 <= 0

    def _register_crossing(self, track_id, history, prev_side, side, now):
        # Cooldown: ignora "tremidas" do ponto em cima da linha logo após um evento
        last = history["last_event_time"]
        if last is not None and (now - last) < self.cooldown_s:
            return

        if prev_side == -1 and side == 1 and history["logical_state"] != "DENTRO":
            self.entradas += 1
            self.entradas_hoje += 1
            history["logical_state"] = "DENTRO"
            history["last_event_time"] = now
            history["entry_time"] = now
            logger.info(f"ID {track_id} ENTROU.")
            self._emit({"evento": "ENTRADA", "track_id": int(track_id), "ts": now,
                        **self._counts()})

        elif prev_side == 1 and side == -1 and history["logical_state"] != "FORA":
            self.saidas += 1
            self.saidas_hoje += 1
            history["logical_state"] = "FORA"
            history["last_event_time"] = now
            event = {"evento": "SAIDA", "track_id": int(track_id), "ts": now,
                     **self._counts()}
            if history["entry_time"] is not None:
                permanencia = now - history["entry_time"]
                event["permanencia_s"] = round(permanencia, 1)
                logger.info(f"ID {track_id} SAIU. Permanência: {permanencia:.1f}s.")
            else:
                logger.info(f"ID {track_id} SAIU.")
            self._emit(event)

    def _take_over_lost_track(self, point, current_ids):
        """
        Quando o tracker troca o ID de uma pessoa, o ID novo aparece perto de onde
        o antigo sumiu. Herdamos o estado do ID perdido mais próximo para não
        contar a mesma pessoa duas vezes.
        """
        best_id, best_dist = None, self.handover_dist
        for tid, hist in self.track_history.items():
            if tid in current_ids or hist["lost_frames"] == 0 or hist["last_point"] is None:
                continue
            dist = math.dist(hist["last_point"], point)
            if dist <= best_dist:
                best_id, best_dist = tid, dist

        if best_id is None:
            return None
        logger.debug(f"Novo ID herdou o estado do ID perdido {best_id} ({best_dist:.0f}px).")
        return self.track_history.pop(best_id)

    def _age_lost_tracks(self, current_ids):
        ids_to_remove = []
        for tid, hist in self.track_history.items():
            if tid not in current_ids:
                hist["lost_frames"] += 1
                if hist["lost_frames"] > self.max_lost_frames:
                    ids_to_remove.append(tid)
        for tid in ids_to_remove:
            del self.track_history[tid]
