```markdown
# 🐾 PetCar AI 项目文档

PetCar AI 是一个基于 **语音交互 + LLM + TTS** 的智能宠物小车项目。它通过服务端部署的强大 AI 模型，为小车提供实时语音识别、自然语言理解和语音合成能力，实现人车流畅的语音对话和动作控制。

---

## 🚀 核心功能

1. **语音唤醒**：小车持续监听麦克风，通过 **SenseVoice (ASR)** 识别触发词（默认为 "小车小车"）。
2. **流式对话**：唤醒后，用户发出指令，**Qwen3-1.7B (LLM)** 实时生成回复。
3. **边听边说**：LLM 的文本回复同步传入 **CosyVoice (TTS)**，生成 PCM 音频流，实时推送到小车扬声器播放。
4. **动作控制**：LLM 的回复中包含结构化的动作指令（例如 `[ACTION:forward(5)]`），由服务端解析后下发给小车端执行。

---

## 🛠️ 技术栈

### 服务端 (RTX 4060 GPU)

| 组件 | 模型/技术 | 作用 |
| :--- | :--- | :--- |
| **ASR** | SenseVoice | 流式语音识别，唤醒词检测。 |
| **LLM** | Qwen3-1.7B (Int4) | 核心对话逻辑，意图理解，动作指令生成。 |
| **TTS** | CosyVoice | 流式语音合成，生成小车回复语音。 |
| **通信** | Python `websockets` | 提供双向 WebSocket 接口，处理音频流和控制指令。 |
| **协调** | `asyncio` | 管理流式数据队列 (`streaming_manager`) 和异步任务。 |

### 小车端 (Raspberry Pi)

| 组件 | 技术/硬件 | 作用 |
| :--- | :--- | :--- |
| **输入** | PyAudio, 麦克风 | 采集 PCM 音频，并上传到服务端。 |
| **VAD** | WebRTC VAD (可选) | 本地语音活动检测，过滤静音，减少带宽占用。 |
| **输出** | PyAudio, 扬声器 | 接收服务端 PCM 流，实时播放。 |
| **通信** | Python `websockets` | WebSocket 客户端，实现音频上传/下载和指令接收。 |
| **控制** | RPi.GPIO (或同类库) | 驱动电机（前进、后退、转向）和控制状态灯。 |

---

## 📦 项目目录结构

```

petcar-ai/
├── server/             \# 服务端 (AI 模型部署与 API)
│ ├── models/           \# ASR/LLM/TTS 引擎
│ ├── pipeline/         \# 语音交互核心逻辑 (ASR-\>LLM-\>TTS)
│ └── api/              \# WebSocket/HTTP 接口
├── car/                \# 小车端 (树莓派客户端)
│ ├── audio/            \# 音频I/O 和 VAD
│ ├── comm/             \# WebSocket 客户端连接管理
│ └── main.py           \# 启动入口和硬件控制
└── README.md

````

---

## ⚙️ 快速启动指南

### 1. 服务端环境准备

1. **安装 CUDA 和 PyTorch**：确保您的 RTX 4060 具备正确的 GPU 驱动和 CUDA/PyTorch 环境。
2. **安装依赖**：
    ```bash
    # 假设使用 Conda/venv 环境
    pip install torch transformers accelerate optimum onnxruntime websockets pyaudio
    # 安装 SenseVoice 和 CosyVoice SDK (请参考官方文档)
    # pip install sensevoice-sdk cosyvoice-sdk
    ```
3. **模型下载**：将 Qwen3-1.7B (量化版)、SenseVoice 和 CosyVoice 模型文件下载到 `server/models` 目录下，并更新 `server/config.py` 中的路径。

### 2. 小车端环境准备 (树莓派)

1. **安装依赖**：
    ```bash
    pip install websockets pyaudio RPi.GPIO
    # 安装 VAD (如果启用)
    # pip install webrtcvad
    ```
2. **硬件连接**：根据 `car/config.py` 中的 `MOTOR_PINS` 配置，连接好麦克风、扬声器和电机驱动板。

### 3. 运行项目

#### 启动服务端

```bash
# 进入服务端目录
cd petcar-ai/server
# 启动 AI 服务和 WebSocket 接口
python run.py
````

*服务启动后会监听配置的 IP 和端口 (默认为 `ws://0.0.0.0:8765`)*

#### 启动小车端

```bash
# 进入小车端目录
cd petcar-ai/car
# 确保 car/config.py 中的 SERVER_HOST 指向服务端 IP
python main.py
```

*小车端将尝试连接服务端，并开始监听麦克风。*

-----

## 🗣️ 交互示例

当小车端启动后，您可以进行以下操作：

1.  **唤醒**：靠近小车，说出 **"小车小车"**。
2.  **发出指令**：紧接着说出您的指令，例如：**"向前走五步"**。

**预期结果：**

  - **服务端**：ASR 识别文本 → LLM 生成回复 "好的，我这就向前走五步。 [ACTION:forward(5)]"
  - **小车端**：扬声器播放 LLM 的语音回复，并根据 `[ACTION:forward(5)]` 指令驱动电机向前移动。

<!-- end list -->

```
```
