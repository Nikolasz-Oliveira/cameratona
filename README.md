# Cameratona

Detecção e contagem de pessoas em câmera IP (RTSP) usando YOLO + rastreamento (BoT-SORT).
As pessoas são reconhecidas apenas **como pessoas**, sem identificar quem é cada uma.

Parte do projeto *Smart Itaipu Parquetec – Módulo IoT – Detecção de pessoas/animais*.

## Estrutura

```
main.py                         # loop principal: câmera -> IA -> regra -> tela
config/
  settings.json                 # configuração versionada (sem senhas)
  settings.local.json           # (opcional, ignorado pelo git) sobrescreve o settings.json
  config_loader.py
core/
  video/rtsp_stream.py          # leitura RTSP em thread, com reconexão automática
  video/renderer.py             # janela OpenCV, desenho da linha com o mouse
  ai/model_factory.py           # detector YOLO + tracker
  analytics/line_strategy.py    # contagem de entradas/saídas por linha
  analytics/strategy_factory.py # escolhe a estratégia pelo settings.json
tools/download_models.py        # baixa os pesos .pt
tests/                          # testes da lógica de contagem
```

## Instalação

```bash
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt   # para GPU, instale o torch com CUDA antes (ver requirements.txt)
python tools/download_models.py   # precisa de internet; salva os .pt na raiz do projeto
```

Os arquivos `.pt` **não** ficam no git. Rode o `download_models.py` em cada máquina
(ou copie os `.pt` manualmente para a raiz do projeto) antes de ir para a rede da câmera.

## Credenciais da câmera

Não coloque usuário/senha no `settings.json`. Use uma das opções:

- **Arquivo local** `config/settings.local.json` (ignorado pelo git):
  ```json
  { "camera": { "ip": "192.168.1.110", "user": "admin", "password": "minha-senha" } }
  ```
- **Variáveis de ambiente**: `CAMERATONA_CAM_USER` e `CAMERATONA_CAM_PASSWORD`.

A senha aparece mascarada (`****`) nos logs.

## Executar

```bash
python main.py
```

| Tecla / mouse      | Ação                                              |
|--------------------|---------------------------------------------------|
| Clique esquerdo    | adiciona ponto da nova linha                      |
| Clique direito     | desfaz último ponto                               |
| Espaço / Enter     | confirma a nova linha (zera o histórico de lados) |
| C                  | cancela o desenho                                 |
| I                  | inverte o sentido de ENTRADA                      |
| Q                  | sai                                               |

A seta amarela no meio da linha mostra o sentido contado como **ENTRADA**.
Para fixar o sentido, use `analytics.invert_direction` no `settings.json`.

## Principais parâmetros (`settings.json`)

| Chave | Descrição |
|---|---|
| `camera.transport` | `udp` (padrão; câmeras com caminho `onvif1`/`onvif2`, tipo Yoosee, só aceitam UDP) ou `tcp` (mais estável em câmeras que suportam) |
| `camera.timeout_s` / `reconnect_delay_s` | timeout da conexão e espera entre reconexões |
| `camera.no_signal_after_s` | segundos sem frame até mostrar "Sem sinal" |
| `analytics.strategy` | estratégia de análise (`line`) |
| `analytics.cooldown_s` | ignora novas travessias do mesmo ID por N segundos (evita "tremidas" na linha) |
| `analytics.max_lost_frames` | frames que um ID sumido continua na memória |
| `analytics.segment_margin_px` | tolerância nas pontas da linha |
| `analytics.id_handover_max_dist_px` | se o tracker trocar o ID, um ID novo a até N px de onde o antigo sumiu herda o estado dele |

## Testes

```bash
python -m unittest discover tests
```
