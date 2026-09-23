import torch
from ultralytics import YOLO
import cv2

class YoloDetector:
    def __init__(self, model_path="yolov8n.pt", conf_threshold=0.4):
        # Seleciona aceleração por GPU se disponível
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        print(f"Carregando YOLOv8 no dispositivo: {self.device.upper()}")
        
        self.model = YOLO(model_path)
        self.model.to(self.device)
        self.conf_threshold = conf_threshold

    def process_frame(self, frame):
        # Executa a inferência com o rastreador acoplado
        # classes=[0] filtra apenas pessoas
        results = self.model.track(
            frame,
            persist=True,
            device=self.device,
            verbose=False,
            classes=[0],
            conf=self.conf_threshold,
            tracker="botsort.yaml"
        )

        detections = []
        annotated_frame = frame.copy()

        # Verifica se há detecções e se IDs foram atribuídos
        if results[0].boxes is not None and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            ids = results[0].boxes.id.cpu().numpy().astype(int)

            for box, track_id in zip(boxes, ids):
                x1, y1, x2, y2 = map(int, box)
                
                # Ponto central inferior (pés) para lógica de cruzamento futura
                center_x = (x1 + x2) // 2
                center_y = y2

                # Estrutura os dados desvinculados da imagem
                detections.append({
                    "id": track_id,
                    "bbox": (x1, y1, x2, y2),
                    "foot_point": (center_x, center_y)
                })

                # Desenha marcações para validação visual
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.circle(annotated_frame, (center_x, center_y), 5, (0, 0, 255), -1)
                cv2.putText(annotated_frame, f"ID: {track_id}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)

        return annotated_frame, detections