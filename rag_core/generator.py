from typing import List, Dict, Any

from models.generator_model import GeneratorModel


def merge_communication(query, documents, max_documents=5, max_length=4000):
    # 提取文档内容
    document_contents = []
    total_length = 0

    for i, doc in enumerate(documents[:max_documents]):
        content = doc.get('content', '')
        # 简单长度控制
        if total_length + len(content) < max_length:
            document_contents.append(content)
            total_length += len(content)
        else:
            # 如果超过长度限制，截断最后一个文档
            remaining_length = max_length - total_length
            if remaining_length > 100:  # 至少保留100字符
                truncated_content = content[:remaining_length] + "..."
                document_contents.append(truncated_content)
            break

    # 构建提示词
    return build_prompt(query, document_contents)


def build_prompt(query, documents_text):
    prompt = f"""你是一位专业的英语学习助手，请根据用户的问题和提供的英语学习资料生成准确、有用的回答。

            用户问题: {query}

            相关学习资料:
            {documents_text}

            请严格按照以下要求回答：
            1. 基于提供的资料内容回答问题，不要编造不存在的信息
            2. 如果资料中有多个相关解释，请整合最相关的内容
            3. 回答要清晰、准确，适合英语学习者理解
            4. 如果资料不足，请说明哪些信息需要补充

            请开始回答："""
    print(f"{prompt}\n\n---\n")
    return prompt


class Generator:
    def __init__(self):
        self.generate_model = GeneratorModel()

    def generate(self, query: str, res: List[Dict[str, Any]]):
        merge_result = merge_communication(query, res)
        return self.generate_model.communicate(merge_result)
