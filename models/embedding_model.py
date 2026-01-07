import os
import logging
import threading
from sentence_transformers import SentenceTransformer
from dotenv import load_dotenv
from openai import OpenAI

load_dotenv()

# 本地模型路径
LOCAL_MODEL = os.getenv('QWEN_EMBEDDING_MODEL')
# 云服务器模型参数
CLOUD_URL = os.getenv('QWEN_EMBEDDING_URL')
CLOUD_KEY = os.getenv('QWEN_EMBEDDING_KEY')
CLOUD_MODEL = os.getenv('QWEN_EMBEDDING_MODEL')


# 配置日志
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class EmbeddingModel:
    _instances = {}  # 支持不同配置的实例
    _lock = threading.Lock()

    def __new__(cls, model_path: str = LOCAL_MODEL, use_cloud: bool = True):
        # 使用配置作为key，支持不同配置的实例
        instance_key = (model_path, use_cloud)
        
        with cls._lock:
            if instance_key not in cls._instances:
                instance = super(EmbeddingModel, cls).__new__(cls)
                instance.model = None
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
                    logging.info("使用云服务器embedding模型")
                else:
                    logging.warning("模型配置不完整，需要手动加载")
                
                cls._instances[instance_key] = instance
            return cls._instances[instance_key]

    def load_model(self, model_path: str = None):
        """加载本地模型（只在第一次调用时执行）"""
        model_path = model_path or self.local_model_path
        if self.model is None and not self.use_cloud and model_path:
            logging.info(f"正在加载本地embedding model: {model_path}")
            try:
                self.model = SentenceTransformer(model_path)
                logging.info("本地embedding model 加载完成")
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
                logging.info("云服务器embedding model 加载完成")
            except Exception as e:
                logging.error(f"加载云服务器模型失败: {str(e)}")
                raise

    def encode(self, texts):
        """编码文本（支持本地模型和云模型）"""
        if self.model is None:
            if self.use_cloud:
                self.load_cloud_model()
            else:
                self.load_model()
        
        if self.use_cloud:
            # 使用云服务器模型
            try:
                response = self.model.embeddings.create(
                    model=self.cloud_config['model'],
                    input=texts,
                    dimensions=768
                )
                # 提取嵌入向量
                if isinstance(texts, list):
                    return [embedding.embedding for embedding in response.data]
                else:
                    return response.data[0].embedding
            except Exception as e:
                logging.error(f"云服务器编码失败: {str(e)}")
                raise
        else:
            # 使用本地模型
            try:
                return self.model.encode(texts,
                                         convert_to_tensor=False,
                                         normalize_embeddings=True,
                                         show_progress_bar=True)
            except Exception as e:
                logging.error(f"本地模型编码失败: {str(e)}")
                raise

    def get_embedding_dimension(self):
        """获取嵌入维度"""
        if self.model is None:
            raise ValueError("模型未加载，请先调用 load_model()")
        
        if self.use_cloud:
            # 云模型返回固定维度
            return 768
        else:
            # 本地模型返回实际维度
            try:
                return self.model.get_sentence_embedding_dimension()
            except Exception as e:
                logging.error(f"获取维度失败: {str(e)}")
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
