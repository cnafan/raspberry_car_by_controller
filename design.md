# 🐾 PetCar AI 项目方案

## 1. 项目概述

PetCar 是一个基于 **语音交互 + LLM + TTS** 的智能宠物小车。

- 用户通过 **语音唤醒 + 语音命令** 与小车交互。
- 小车通过 **语音回复 + 动作执行** 进行反馈。
- 所有 AI 模型（ASR / LLM / TTS）均在 **服务端 RTX 4060** 部署，  
  小车端仅作为 **输入输出终端**。

核心模型组合：

- **ASR**: SenseVoice (流式识别 + 触发词)
- **LLM**: Qwen3-1.7B (量化，流式对话)
- **TTS**: CosyVoice (流式语音合成)

---

## 2. 项目目录结构

petcar-ai/
├── server/ # 服务端 (4060 GPU)
│ ├── models/ # 模型加载与推理
│ │ ├── asr_engine.py # SenseVoice (ASR)
│ │ ├── llm_engine.py # Qwen3 (LLM)
│ │ ├── tts_engine.py # CosyVoice (TTS)
│ │ └── init.py
│ ├── pipeline/ # 语音交互流水线
│ │ ├── conversation.py # ASR → LLM → TTS 主逻辑
│ │ ├── streaming_manager.py # 流式数据管理
│ │ └── init.py
│ ├── api/ # 通信接口 (小车 ↔ 服务端)
│ │ ├── server.py # WebSocket/HTTP 服务
│ │ └── protocol.py # 数据协议定义
│ ├── config.py # 模型/系统配置
│ └── run.py # 启动入口
│
├── car/ # 小车端 (树莓派)
│ ├── audio/ # 音频输入输出
│ │ ├── mic_client.py # 录音并发送音频流
│ │ ├── speaker_client.py # 播放服务端返回的音频流
│ │ └── vad.py # 本地简单语音检测 (可选)
│ ├── control/ # 电机 & 动作控制
│ │ ├── motor_driver.py # TB6612FNG 电机驱动封装
│ │ ├── car_controller.py # 高层动作 (前进/后退/转向)
│ │ └── init.py
│ ├── comm/ # 通信
│ │ ├── client.py # 与服务端的 WebSocket 客户端
│ │ └── init.py
│ ├── config.py # 硬件配置 (GPIO, 音频设备等)
│ └── main.py # 小车端启动入口
│
├── docs/ # 文档与说明
│ ├── architecture.md # 系统架构图
│ └── api_protocol.md # 通信协议说明
│
└── README.md

---

## 3. 文件内容详情

### 3.1 服务端（server）

#### `models/asr_engine.py`

- 加载 **SenseVoice** 模型。
- 提供接口：
  - `transcribe_stream(audio_chunk) -> str`
  - `detect_wakeup_word(text) -> bool`

#### `models/llm_engine.py`

- 加载 **Qwen3-1.7B (量化版)**。
- 提供流式对话接口：
  - `chat_stream(history, new_input) -> Generator[str]`

#### `models/tts_engine.py`

- 加载 **CosyVoice**。
- 提供接口：
  - `synthesize_stream(text) -> Generator[pcm_chunk]`

---

#### `pipeline/conversation.py`

- 主控制逻辑：
  1. 处理语音流 → ASR 转写。
  2. 触发词检测 → 激活 LLM。
  3. LLM 流式输出 → 同步传入 TTS。
  4. TTS 流式 PCM 输出 → 返回给小车端播放。

#### `pipeline/streaming_manager.py`

- 管理流式数据队列：
  - `AudioQueue`（PCM 输入缓存）
  - `TextQueue`（ASR → LLM → TTS 中间结果）
  - `PCMQueue`（TTS 输出 → 小车播放）

---

#### `api/server.py`

- 提供 **WebSocket 服务**：
  - `/audio/in` → 接收小车端音频流。
  - `/audio/out` → 推送合成语音流。
  - `/control` → 下发动作指令（前进/转向等）。

#### `api/protocol.py`

- 定义通信协议：
  - `AudioFrame { seq, pcm_data }`
  - `TextFrame { seq, text }`
  - `ControlCmd { type, value }`

---

#### `run.py`

- 初始化模型、启动 API 服务。

---

### 3.2 小车端（car）

#### `audio/mic_client.py`

- 采集麦克风音频，按帧编码并推送到服务端。
- 支持 **VAD (vad.py)** 来避免空闲传输。

#### `audio/speaker_client.py`

- 从服务端接收 PCM 流，实时写入播放设备。

#### `control/motor_driver.py`

- TB6612FNG 电机控制封装。
- 接口：`set_motor_speed(left, right)`。

#### `control/car_controller.py`

- 高层动作接口：`forward()`, `backward()`, `turn_left()`, `turn_right()`。

#### `comm/client.py`

- WebSocket 客户端，与服务端保持连接。
- 通道：
  - `audio_in`（上传音频）
  - `audio_out`（接收合成语音）
  - `control`（接收动作指令）

#### `main.py`

- 启动逻辑：
  1. 连接服务端。
  2. 启动音频录制/播放线程。
  3. 启动电机控制监听。

---

## 4. 数据流交互

1. **用户语音 → 小车麦克风 → 服务端 ASR**
2. **ASR → 文本 → 触发词检测 → 进入对话模式**
3. **文本 → LLM → 生成回复**
4. **LLM 输出 → TTS → PCM 音频流 → 小车扬声器**
5. **LLM 输出中的动作指令 → 下发到小车 → 电机控制**

---

## 5. 开发建议

- 优先实现 **流式音频链路 (ASR → TTS)**，确保延迟可控。
- 再接入 **LLM 流式回复**，保证小车能边听边说。
- 最后实现 **动作控制协议**，让小车能根据语音指令行动。
