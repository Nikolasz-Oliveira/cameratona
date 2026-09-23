import torch
from ultralytics import YOLO
import cv2
from core.ai.detector_base import BaseDetector
from config.config_loader import Config
from utils.logger import logger

class YoloStandardDetector(BaseDetector):
    def __init__(self):
        ai_config = Config.ai
        model_path = ai_config.get("model_name", "yolov8n.pt")
        self.conf_threshold = ai_config.get("confidence", 0.45)
        
        # Override para device configurado no JSON ou auto-detect
        cfg_device = ai_config.get("device", "cuda")
        self.device = cfg_device if torch.cuda.is_available() else "cpu"
        
        logger.info(f"Carregando {model_path} no dispositivo: {self.device.upper()}")
        self.model = YOLO(model_path)
        self.model.to(self.device)

    def process_frame(self, frame):
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

        if results[0].boxes is not None and results[0].boxes.id is not None:
            boxes = results[0].boxes.xyxy.cpu().numpy()
            ids = results[0].boxes.id.cpu().numpy().astype(int)

            for box, track_id in zip(boxes, ids):
                x1, y1, x2, y2 = map(int, box)
                center_x = (x1 + x2) // 2
                center_y = y2

                detections.append({
                    "id": track_id,
                    "bbox": (x1, y1, x2, y2),
                    "foot_point": (center_x, center_y)
                })

                # Apenas desenha a caixa de detecção. 
                # Linhas, polígonos e textos de contagem serão desenhados pelo Renderer.
                color = Config.ui.get("colors", {}).get("bounding_box", [0, 255, 0])
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), tuple(color), 2)
                cv2.circle(annotated_frame, (center_x, center_y), 5, (0, 0, 255), -1)
                cv2.putText(annotated_frame, f"ID: {track_id}", (x1, y1 - 10),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.6, tuple(color), 2)

        return annotated_frame, detections


class DetectorFactory:
    @staticmethod
    def create_detector() -> BaseDetector:
        # No futuro, se a config pedir "reid" ou "facial", 
        # a Factory instanciará classes diferentes aqui.
        logger.info("Construindo detector padrão (YOLO sem ReID).")
        return YoloStandardDetector()