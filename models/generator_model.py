import os
import logging
import threading
from dotenv import load_dotenv
from transformers import AutoTokenizer, AutoModelForCausalLM
from openai import OpenAI

load_dotenv()

# 本地模型路径
LOCAL_MODEL = os.getenv('QWEN_MODEL')

# 云服务器模型参数
CLOUD_URL = os.getenv("QWEN_URL")
CLOUD_KEY = os.getenv("QWEN_KEY")
CLOUD_MODEL = os.getenv("QWEN_MODEL")

# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class GeneratorModel:
    _instances = {}  # 支持不同配置的实例
    _lock = threading.Lock()

    def __new__(cls, model_path: str = LOCAL_MODEL, use_cloud: bool = True):
        # 使用配置作为key，支持不同配置的实例
        instance_key = (model_path, use_cloud)
        
        with cls._lock:
            if instance_key not in cls._instances:
                instance = super(GeneratorModel, cls).__new__(cls)
                instance.model = None
                instance.tokenizer = None
                instance.use_cloud = use_cloud
                instance.cloud_config = {
                    'url': CLOUD_URL,
                    'key': CLOUD_KEY,
                    'model': CLOUD_MODEL
                }
                instance.local_model_path = model_path
                
                if not use_cloud and model_path:
                    instance.load_model(model_path)
                elif use_cloud and all(instance.cloud_config.values()):
                    instance.load_cloud_model()
                    logging.info("使用云服务器generator模型")
                else:
                    logging.warning("模型配置不完整，需要手动加载")
                
                cls._instances[instance_key] = instance
            return cls._instances[instance_key]

    def load_model(self, model_path: str = None):
        """加载本地模型（只在第一次调用时执行）"""
        model_path = model_path or self.local_model_path
        if self.model is None and not self.use_cloud and model_path:
            logging.info(f"正在加载本地generator model: {model_path}")
            try:
                self.tokenizer = AutoTokenizer.from_pretrained(model_path)
                self.model = AutoModelForCausalLM.from_pretrained(
                    model_path,
                    dtype="auto",
                )
                logging.info(f"本地generator model 加载完成: {model_path}")
            except Exception as e:
                logging.error(f"加载本地模型失败: {str(e)}")
                raise

    def load_cloud_model(self):
        """加载云服务器模型（只在第一次调用时执行）"""
        if self.model is None and self.use_cloud:
            if not all(self.cloud_config.values()):
                raise ValueError("云服务器配置不完整")
            
            try:
                self.model = OpenAI(
                    base_url=self.cloud_config['url'],
                    api_key=self.cloud_config['key'],
                )
                logging.info("云服务器generator model 加载完成")
            except Exception as e:
                logging.error(f"加载云服务器模型失败: {str(e)}")
                raise

    def communicate(self, prompt, **kwargs):
        """与模型通信（支持本地模型和云模型）"""
        if self.model is None:
            if self.use_cloud:
                self.load_cloud_model()
            else:
                self.load_model()
        
        if self.use_cloud:
            # 使用云服务器模型
            try:
                messages = [
                    {"role": "user", "content": prompt}
                ]
                
                response = self.model.chat.completions.create(
                    model=self.cloud_config['model'],
                    messages=messages,
                    temperature=kwargs.get('temperature', 0.7),
                    max_tokens=kwargs.get('max_tokens', 4000),
                    stream=False
                )
                
                # 云模型没有thinking content，返回空字符串
                thinking_content = ""
                content = response.choices[0].message.content.strip("\n")
                return thinking_content, content
            except Exception as e:
                logging.error(f"云服务器通信失败: {str(e)}")
                raise
        else:
            # 使用本地模型
            try:
                messages = [
                    {"role": "user", "content": prompt}
                ]

                text = self.tokenizer.apply_chat_template(
                    messages,
                    tokenize=False,
                    add_generation_prompt=True,
                    enable_thinking=True
                )
                model_inputs = self.tokenizer([text], return_tensors="pt")
                # conduct text completion
                generated_ids = self.model.generate(
                    **model_inputs,
                    max_new_tokens=kwargs.get('max_tokens', 32768)
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
            except Exception as e:
                logging.error(f"本地模型通信失败: {str(e)}")
                raise

    def is_using_cloud(self):
        """返回是否使用云服务器模型"""
        return self.use_cloud

    def get_config(self):
        """获取当前配置"""
        if self.use_cloud:
            return {
                'type': 'cloud',
                'config': self.cloud_config
            }
        else:
            return {
                'type': 'local',
                'model_path': self.local_model_path,
                'model_loaded': self.model is not None
            }

    def clear_instance(self):
        """清除当前实例"""
        instance_key = (self.local_model_path, self.use_cloud)
        with self._lock:
            if instance_key in self._instances:
                del self._instances[instance_key]
                logging.info("实例已清除")

    @classmethod
    def clear_all_instances(cls):
        """清除所有实例"""
        with cls._lock:
            cls._instances.clear()
            logging.info("所有实例已清除")
