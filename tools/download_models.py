import os
from pathlib import Path

from ultralytics import YOLO

# Salva os pesos na raiz do projeto, independentemente de onde o script é executado
PROJECT_ROOT = Path(__file__).resolve().parent.parent

def baixar_modelos():
    os.chdir(PROJECT_ROOT)
    print("Iniciando download dos modelos. Certifique-se de ter internet...")
    
    # O YOLO fará o download do arquivo .pt se não o encontrar na pasta local
    print("\nBaixando YOLOv8 Nano...")
    YOLO("yolov8n.pt")
    
    print("\nBaixando YOLO26 Nano (modelo padrão do settings.json)...")
    YOLO("yolo26n.pt")
    
    print("\n[OK] Downloads concluídos! Os arquivos .pt estão na raiz do projeto.")
    print("Você já pode se conectar à rede restrita da câmera IP.")

if __name__ == "__main__":
    baixar_modelos()