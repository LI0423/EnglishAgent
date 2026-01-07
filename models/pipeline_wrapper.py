from typing import Dict, List, Optional
import os
from transformers import AutoModelForCausalLM, AutoTokenizer, StoppingCriteria, StoppingCriteriaList, TextStreamer, pipeline
from langchain_huggingface import HuggingFacePipeline

from dotenv import load_dotenv

load_dotenv()

class QwenPipelineWrapper:
    def __init__(self,
                 model_path: str = os.getenv('QWEN_MODEL'),
                 max_new_tokens: int = 4096,
                 device: Optional[str] = 'mps',
                 temperature: float = 0.7,
                 enable_thinking: bool = True,
                 use_streamer: bool = True):
        self.model_path = model_path
        self.enable_thinking = enable_thinking
        self.max_new_tokens = max_new_tokens
        self.device = device
        self.tokenizer = AutoTokenizer.from_pretrained(model_path, trust_remote_code=True)
        self.model = AutoModelForCausalLM.from_pretrained(
            model_path,
            trust_remote_code=True
        )
        self.stopping_criteria = self._create_stopping_criteria() if enable_thinking else None
        self.streamer = TextStreamer(self.tokenizer, skip_prompt=True) if use_streamer else None
        self.pipeline = self._create_pipeline(temperature)
        self.langchain_llm = HuggingFacePipeline(pipeline=self.pipeline)

    def _create_stopping_criteria(self):
        class ThinkingStoppingCriteria(StoppingCriteria):
            def __init__(self, tokenizer, thinking_end_token=151668):
                self.tokenizer = tokenizer
                self.thinking_end_token = thinking_end_token
                self.thinking_ended = False
            
            def __call__(self, input_ids, scores, **kwargs):
                if self.thinking_end_token in input_ids[0]:
                    self.thinking_ended = True
                return False
        return StoppingCriteriaList([ThinkingStoppingCriteria(self.tokenizer)])
    
    def _create_pipeline(self, temperature):
        generation_config = {
            "max_new_tokens": self.max_new_tokens,
            "temperature": temperature,
            "top_p": 0.95,
            "do_sample": temperature > 0,
            "pad_token_id": self.tokenizer.pad_token_id or self.tokenizer.eos_token_id,
            "eos_token_id": self.tokenizer.eos_token_id
        }
    
        if self.enable_thinking:
            generation_config.update({
                "stopping_criteria": self.stopping_criteria
            })

        pipe = pipeline(
            "text-generation",
            model=self.model,
            tokenizer=self.tokenizer,
            device=self.device,
            **generation_config
        )
        return pipe
    
    def format_prompt_with_thinking(self, messages: List[Dict]) -> str:
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
            enable_thinking=self.enable_thinking
        )
        return text
    
    def generate_with_thinking(
            self,
            prompt: str,
            return_thinking: bool = True,
    ) -> Dict[str, str]:
        messages = [{"role": "user", "content": prompt}]
        formatted_prompt = self.format_prompt_with_thinking(messages)

        result = self.pipeline(
            formatted_prompt,
            return_full_text=False
        )

        full_output = result[0]['generated_text']

        if self.enable_thinking and return_thinking:
            thinking_content, final_content = self._parse_thinking_output(full_output)
        else:
            thinking_content, final_content = "", full_output

        return {
            "thinking": thinking_content,
            "content": final_content,
            "full_output": full_output
        }
    
    def _parse_thinking_output(self, text: str) -> tuple:
        thinking_end_tag = "</think>"
        if thinking_end_tag in text:
            parts = text.split(thinking_end_tag, 1)
            thinking_content = parts[0].replace("<thinking>", "").strip()
            final_content = parts[1].strip() if len(parts) > 1 else ""
        else:
            thinking_content = ""
            final_content = text.strip()
        return thinking_content, final_content
    
    def get_langchain_llm(self):
        return self.langchain_llm
    
    def chat(self, message: str, history: List[Dict] = None) -> str:
        if history is None:
            history = []
        
        messages = history + [{"role": "user", "content": message}]
        formatted_prompt = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True
        )
        result = self.pipeline(formatted_prompt, return_full_text=False)
        return result[0]['generated_text']

if __name__ == '__main__':
    # 2. 初始化 Qwen 包装器
    print("正在初始化 Qwen 模型...")
    model_wrapper = QwenPipelineWrapper(
        device="mps",  # 自动选择设备
        max_new_tokens=2048,
        temperature=0.7,
        enable_thinking=True,
        use_streamer=False
    )

    # 3. 获取 LangChain LLM
    qwen_llm = model_wrapper.get_langchain_llm()

    # 4. 测试基础功能
    print("\n测试基础生成功能...")
    test_prompt = "请解释一下机器学习的基本概念"
    test_result = qwen_llm.invoke(test_prompt)
    print(f"测试回复: {test_result[:200]}...\n")

    # 5. 测试思维链功能
    print("测试思维链功能...")
    thinking_result = model_wrapper.generate_with_thinking(
        "如果我有3个苹果，吃了1个，又买了5个，现在有多少个苹果？"
    )
    print(f"思维过程: {thinking_result['thinking']}")
    print(f"最终回答: {thinking_result['content']}\n")