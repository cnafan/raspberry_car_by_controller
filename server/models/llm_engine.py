import time
from typing import Generator, List, Dict, Any

# 假设使用 Hugging Face transformers 和 Qwen 库
try:
    from transformers import AutoModelForCausalLM, AutoTokenizer
    import torch
    # 假设 Qwen3-1.7B 量化后模型加载
except ImportError:
    print("Warning: transformers or torch not found. Using mock implementation for LLM.")
    
    class MockTokenizer:
        def encode(self, text, *args, **kwargs):
            return list(text.encode('utf-8'))
        def decode(self, tokens, *args, **kwargs):
            return "".join([str(t) for t in tokens])
        def apply_chat_template(self, history, tokenize=False, add_generation_prompt=True):
            # 模拟对话模板，简化处理
            formatted_input = ""
            for msg in history:
                role = "User" if msg["role"] == "user" else "Assistant"
                formatted_input += f"<{role}>: {msg['content']}\n"
            return formatted_input

class LLMEngine:
    """
    Qwen3-1.7B (量化版) 模型引擎。
    负责流式对话生成。
    """
    
    def __init__(self, model_path: str, quantization_config: Dict[str, Any] = None):
        """
        初始化 LLM 引擎。
        :param model_path: Qwen 模型文件路径。
        :param quantization_config: 量化配置（如 QLoRA, AWQ 等）。
        """
        print(f"Initializing LLMEngine with model: {model_path}")
        self.model_path = model_path
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        
        try:
            # 真实部署时，这里会加载量化后的模型
            self.tokenizer = AutoTokenizer.from_pretrained(model_path)
            self.model = AutoModelForCausalLM.from_pretrained(
                model_path,
                device_map=self.device,
                torch_dtype=torch.bfloat16, # 假设使用 bfloat16
                # **quantization_config # 实际传入量化配置
            )
            self.is_mock = False
        except Exception as e:
            print(f"Failed to load LLM model ({e}). Falling back to mock implementation.")
            self.tokenizer = MockTokenizer()
            self.is_mock = True
            
        self.system_prompt = (
            "你是一个智能宠物小车 AI 助手，名叫 PetCar。你的任务是和用户进行语音交互，"
            "并执行简单的物理动作。你的回答应该简短、友好且直接。如果需要执行动作，"
            "请在回复中包含一个结构化指令，例如：`[ACTION:forward(5)]`。"
            "可用动作为：forward(steps), backward(steps), turn_left(degrees), turn_right(degrees), stop()."
        )
        self.history: List[Dict[str, str]] = [{"role": "system", "content": self.system_prompt}]
        print(f"LLM Engine initialized on device: {self.device}")


    def chat_stream(self, new_input: str) -> Generator[str, None, None]:
        """
        与 LLM 进行流式对话。
        
        :param new_input: 用户的新输入文本。
        :return: 文本块的生成器 (Generator[str])。
        """
        # 1. 更新对话历史
        self.history.append({"role": "user", "content": new_input})
        
        if self.is_mock:
            # --- 模拟流式输出 ---
            print(f"Mock LLM received input: {new_input}")
            mock_response = self._get_mock_response(new_input)
            
            # 模拟流式生成
            for char in mock_response:
                time.sleep(0.05) # 模拟生成延迟
                yield char
            
            # 2. 更新历史（模拟 LLM 完整回复）
            self.history.append({"role": "assistant", "content": mock_response})
            return

        # --- 真实 LLM 逻辑 ---
        # 1. 格式化输入，应用 Qwen 的 ChatML 模板
        # 实际 API 需要根据具体的 Qwen 模型版本调整
        messages = self.history
        
        # 2. 转换为模型输入
        input_text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True # 确保最后是 assistant 的 token
        )
        
        inputs = self.tokenizer.encode(input_text, return_tensors="pt").to(self.device)
        
        # 3. 流式生成
        streamer = self.model.generate(
            inputs,
            max_length=512,
            do_sample=True,
            top_p=0.8,
            temperature=0.7,
            repetition_penalty=1.03,
            # stream=True # 依赖于具体的 transformers 版本或自定义 Streamer
        )
        
        full_response = ""
        # 实际中需要一个自定义 Streamer 来实现按 token 输出
        # 这里用一个简化的同步生成并分字返回
        generated_ids = streamer
        
        for token_id in generated_ids:
            new_text = self.tokenizer.decode([token_id], skip_special_tokens=True)
            if new_text:
                yield new_text
                full_response += new_text
                
        # 4. 更新历史（真实 LLM 完整回复）
        self.history.append({"role": "assistant", "content": full_response})


    def _get_mock_response(self, input_text: str) -> str:
        """根据输入模拟 LLM 的回复，包含动作指令。"""
        lower_input = input_text.lower()
        
        if "前进" in lower_input or "向前" in lower_input:
            return "好的，我这就向前走五步。 [ACTION:forward(5)]"
        elif "转向" in lower_input or "左转" in lower_input:
            return "收到！正在向左转 90 度。 [ACTION:turn_left(90)]"
        elif "你好" in lower_input or "嗨" in lower_input:
            return "你好呀！我是 PetCar，很高兴为你服务。你想让我去哪儿玩呢？"
        elif "天气" in lower_input or "怎么样" in lower_input:
            return "我现在无法获取天气信息，但我知道今天是个和你玩的好日子！"
        elif "停止" in lower_input or "停下" in lower_input:
            return "明白，立即停止！ [ACTION:stop()]"
        else:
            return "嗯... 我好像没听懂你的意思，请再说一遍好吗？"

    def get_history(self) -> List[Dict[str, str]]:
        """获取当前对话历史。"""
        return self.history
        
    def clear_history(self):
        """清空对话历史，仅保留系统提示词。"""
        self.history = [{"role": "system", "content": self.system_prompt}]
        print("LLM History cleared.")


if __name__ == '__main__':
    # 示例用法
    MOCK_LLM_MODEL_PATH = "/path/to/qwen3-1.7b-quantized"
    
    llm_engine = LLMEngine(model_path=MOCK_LLM_MODEL_PATH)
    
    print("\n--- Dialogue 1: Command ---")
    user_input_1 = "小车小车，请向前走五步。"
    print(f"User: {user_input_1}")
    
    response_stream = llm_engine.chat_stream(user_input_1)
    full_response_1 = ""
    print("PetCar: ", end="", flush=True)
    for chunk in response_stream:
        print(chunk, end="", flush=True)
        full_response_1 += chunk
    print("\n")
    
    
    print("\n--- Dialogue 2: Free Chat ---")
    user_input_2 = "你觉得我今天该做什么？"
    print(f"User: {user_input_2}")
    
    response_stream = llm_engine.chat_stream(user_input_2)
    full_response_2 = ""
    print("PetCar: ", end="", flush=True)
    for chunk in response_stream:
        print(chunk, end="", flush=True)
        full_response_2 += chunk
    print("\n")
    
    # 清空历史，开始新一轮对话
    llm_engine.clear_history()
