import time
from core.analytics.strategy_interface import AnalyticsStrategy
from config.config_loader import Config
from utils.logger import logger

class LineStrategy(AnalyticsStrategy):
    def __init__(self):
        geom = Config.analytics.get("geometry", {})
        self.p1 = tuple(geom.get("line_p1", [730, 400]))
        self.p2 = tuple(geom.get("line_p2", [850, 400]))
        
        self.entradas = 0
        self.saidas = 0
        self.track_history = {}
        self.max_lost_frames = Config.analytics.get("max_lost_frames", 30)

    def get_geometry(self):
        return [self.p1, self.p2]

    def get_stats(self):
        return self.entradas, self.saidas

    def _side_of_line(self, point):
        x, y = point
        value = (self.p2[0] - self.p1[0]) * (y - self.p1[1]) - (self.p2[1] - self.p1[1]) * (x - self.p1[0])
        return 1 if value > 0 else -1 if value < 0 else 0

    def _is_within_segment_bounds(self, x):
        min_x = min(self.p1[0], self.p2[0]) - 50
        max_x = max(self.p1[0], self.p2[0]) + 50
        return min_x <= x <= max_x

    def update(self, detections):
        current_ids = set()
        now = time.time()

        for det in detections:
            track_id = det["id"]
            point = det["foot_point"]
            current_ids.add(track_id)

            if not self._is_within_segment_bounds(point[0]):
                continue

            side = self._side_of_line(point)
            if side == 0:
                continue

            if track_id not in self.track_history:
                self.track_history[track_id] = {
                    "last_side": side, "logical_state": "DESCONHECIDO",
                    "events": [], "lost_frames": 0
                }
                continue

            history = self.track_history[track_id]
            previous_side = history["last_side"]

            if previous_side != side:
                if previous_side == -1 and side == 1:
                    if history["logical_state"] != "DENTRO":
                        self.entradas += 1
                        history["logical_state"] = "DENTRO"
                        history["events"].append({"tipo": "ENTRADA", "tempo": now})
                        logger.info(f"ID {track_id} ENTROU na sala.")
                        
                elif previous_side == 1 and side == -1:
                    if history["logical_state"] != "FORA":
                        self.saidas += 1
                        history["logical_state"] = "FORA"
                        history["events"].append({"tipo": "SAIDA", "tempo": now})
                        
                        entradas = [e for e in history["events"] if e["tipo"] == "ENTRADA"]
                        if entradas:
                            permanencia = now - entradas[-1]["tempo"]
                            logger.info(f"ID {track_id} SAIU. Permanência: {permanencia:.1f}s.")

                history["last_side"] = side
            history["lost_frames"] = 0

        ids_to_remove = []
        for tid, hist in self.track_history.items():
            if tid not in current_ids:
                hist["lost_frames"] = hist.get("lost_frames", 0) + 1
                if hist["lost_frames"] > self.max_lost_frames:
                    ids_to_remove.append(tid)
                    
        for tid in ids_to_remove:
            del self.track_history[tid]

    def set_geometry(self, points):
        if len(points) >= 2:
            self.p1 = tuple(points[0])
            self.p2 = tuple(points[1])
            logger.info(f"Geometria da Linha atualizada para: {self.p1} -> {self.p2}")
            # Dica: Em um projeto mais avançado, você pode salvar isso de volta no settings.json aqui.