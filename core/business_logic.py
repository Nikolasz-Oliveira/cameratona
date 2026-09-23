import time

class LineCounter:
    def __init__(self, p1, p2):
        self.p1 = p1
        self.p2 = p2
        self.entradas = 0
        self.saidas = 0
        
        # Estrutura unificada: Guarda estado, lado da linha, frames perdidos e log de eventos
        self.track_history = {}
        self.max_lost_frames = 30

    def update_line(self, p1, p2):
        self.p1 = p1
        self.p2 = p2

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

            # Novo ID detectado: inicializa o registro
            if track_id not in self.track_history:
                self.track_history[track_id] = {
                    "last_side": side,
                    "logical_state": "DESCONHECIDO", # Pode ser 'DENTRO', 'FORA' ou 'DESCONHECIDO'
                    "events": [], # Guarda o histórico: [{"tipo": "ENTRADA", "tempo": timestamp}, ...]
                    "lost_frames": 0
                }
                continue

            history = self.track_history[track_id]
            previous_side = history["last_side"]

            # Detectou cruzamento da linha
            if previous_side != side:
                
                # Sentido de Entrada
                if previous_side == -1 and side == 1:
                    # Só contabiliza se a pessoa não estiver já "DENTRO"
                    if history["logical_state"] != "DENTRO":
                        self.entradas += 1
                        history["logical_state"] = "DENTRO"
                        history["events"].append({"tipo": "ENTRADA", "tempo": now})
                        print(f"[LOG] ID {track_id} ENTROU na sala.")
                        
                # Sentido de Saída
                elif previous_side == 1 and side == -1:
                    # Só contabiliza se a pessoa não estiver já "FORA"
                    if history["logical_state"] != "FORA":
                        self.saidas += 1
                        history["logical_state"] = "FORA"
                        history["events"].append({"tipo": "SAIDA", "tempo": now})
                        
                        # Calcula tempo de permanência baseado no último evento de entrada
                        entradas_anteriores = [e for e in history["events"] if e["tipo"] == "ENTRADA"]
                        if entradas_anteriores:
                            ultima_entrada = entradas_anteriores[-1]["tempo"]
                            permanencia = now - ultima_entrada
                            print(f"[LOG] ID {track_id} SAIU. Tempo de permanência: {permanencia:.1f} segundos.")
                        else:
                            print(f"[LOG] ID {track_id} SAIU (Entrada não registrada).")

                # Atualiza o último lado físico conhecido
                history["last_side"] = side
                
            # Zera o contador de perda de rastro, pois a pessoa foi vista neste frame
            history["lost_frames"] = 0

        # Limpeza de IDs que sumiram definitivamente
        ids_to_remove = []
        for tid, hist in self.track_history.items():
            if tid not in current_ids:
                hist["lost_frames"] += 1
                if hist["lost_frames"] > self.max_lost_frames:
                    ids_to_remove.append(tid)
                    
        for tid in ids_to_remove:
            # Aqui, futuramente, você pode pegar a lista `self.track_history[tid]["events"]`
            # e salvar em um banco de dados antes de deletar da memória.
            del self.track_history[tid]