import threading

from transformers import AutoTokenizer, AutoModelForCausalLM

MODEL_PATH = "/Users/litengjiang/.cache/modelscope/hub/models/Qwen/Qwen3-0.6B"


class GeneratorModel:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, model_path: str = MODEL_PATH):
        with cls._lock:
            if cls._instance is None:
                cls._instance = super(GeneratorModel, cls).__new__(cls)
                cls._instance.model = None
                if model_path:
                    cls._instance.load_model(model_path)
            return cls._instance

    def load_model(self, model_path: str):
        """加载模型（只在第一次调用时执行）"""
        if self.model is None:
            print(f"正在加载模型: {model_path}")
            self.tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
            self.model = AutoModelForCausalLM.from_pretrained(
                MODEL_PATH,
                torch_dtype="auto",
            )
            print("模型加载完成")

    def communicate(self, prompt):
        messages = [
            {"role": "user", "content": prompt}
        ]

        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=True  # Switches between thinking and non-thinking modes. Default is True.
        )
        model_inputs = self.tokenizer([text], return_tensors="pt").to(self.model.device)
        # conduct text completion
        generated_ids = self.model.generate(
            **model_inputs,
            max_new_tokens=32768
        )
        output_ids = generated_ids[0][len(model_inputs.input_ids[0]):].tolist()
        # parsing thinking content
        try:
            # rindex finding 151668 (</think>)
            index = len(output_ids) - output_ids[::-1].index(151668)
        except ValueError:
            index = 0

        thinking_content = self.tokenizer.decode(output_ids[:index], skip_special_tokens=True).strip("\n")
        content = self.tokenizer.decode(output_ids[index:], skip_special_tokens=True).strip("\n")
        return thinking_content, content
