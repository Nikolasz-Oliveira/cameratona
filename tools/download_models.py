from ultralytics import YOLO

def baixar_modelos():
    print("Iniciando download dos modelos. Certifique-se de ter internet...")
    
    # O YOLO fará o download do arquivo .pt se não o encontrar na pasta local
    print("\nBaixando YOLOv8 Nano...")
    YOLO("yolov8n.pt")
    
    print("\nBaixando YOLOv10 Nano (Performance superior)...")
    YOLO("yolo26n.pt")
    
    print("\n[OK] Downloads concluídos! Os arquivos .pt estão na raiz do projeto.")
    print("Você já pode se conectar à rede restrita da câmera IP.")

if __name__ == "__main__":
    baixar_modelos()