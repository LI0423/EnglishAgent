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


def build_prompt(query, documents_text, module="general"):
    # 为不同模块定制提示词
    module_prompts = {
        "vocabulary": f"""你是一位专业的词汇学习助手，请根据用户的问题和提供的英语词汇资料生成准确、详细的回答。

            用户问题: {query}

            相关词汇资料:
            {documents_text}

            请严格按照以下要求回答：
            1. 基于提供的资料内容回答问题，不要编造不存在的信息
            2. 提供详细的词汇释义、例句和用法
            3. 分析词汇的词根词缀，帮助用户记忆
            4. 提供词汇的同义词、反义词和搭配
            5. 回答要清晰、准确，适合英语学习者理解

            请开始回答：""",
        "reading": f"""你是一位专业的阅读指导助手，请根据用户的问题和提供的阅读资料生成准确、有用的回答。

            用户问题: {query}

            相关阅读资料:
            {documents_text}

            请严格按照以下要求回答：
            1. 基于提供的资料内容回答问题，不要编造不存在的信息
            2. 分析文章的结构和主题
            3. 提供阅读技巧和策略建议
            4. 分析文章中的长难句和重点词汇
            5. 回答要清晰、准确，适合英语学习者理解

            请开始回答：""",
        "writing": f"""你是一位专业的写作指导助手，请根据用户的问题和提供的写作资料生成准确、有用的回答。

            用户问题: {query}

            相关写作资料:
            {documents_text}

            请严格按照以下要求回答：
            1. 基于提供的资料内容回答问题，不要编造不存在的信息
            2. 提供详细的写作指导和建议
            3. 分析写作中的常见错误和改进方法
            4. 提供写作模板和范例
            5. 回答要清晰、准确，适合英语学习者理解

            请开始回答：""",
        "speaking": f"""你是一位专业的口语指导助手，请根据用户的问题和提供的口语资料生成准确、有用的回答。

            用户问题: {query}

            相关口语资料:
            {documents_text}

            请严格按照以下要求回答：
            1. 基于提供的资料内容回答问题，不要编造不存在的信息
            2. 提供详细的口语练习建议和技巧
            3. 分析口语中的常见错误和改进方法
            4. 提供口语范例和表达方式
            5. 回答要清晰、准确，适合英语学习者理解

            请开始回答：""",
        "deep_search": f"""你是一位专业的深度搜索助手，请根据用户的问题和提供的搜索资料生成准确、全面的回答。

            用户问题: {query}

            相关搜索资料:
            {documents_text}

            请严格按照以下要求回答：
            1. 基于提供的资料内容回答问题，不要编造不存在的信息
            2. 整合所有相关信息，提供全面的回答
            3. 分析信息的可靠性和相关性
            4. 提供详细的信息来源和参考
            5. 回答要清晰、准确，适合英语学习者理解

            请开始回答："""
    }
    
    # 默认提示词
    default_prompt = f"""你是一位专业的英语学习助手，请根据用户的问题和提供的英语学习资料生成准确、有用的回答。

            用户问题: {query}

            相关学习资料:
            {documents_text}

            请严格按照以下要求回答：
            1. 基于提供的资料内容回答问题，不要编造不存在的信息
            2. 如果资料中有多个相关解释，请整合最相关的内容
            3. 回答要清晰、准确，适合英语学习者理解
            4. 如果资料不足，请说明哪些信息需要补充

            请开始回答："""
    
    prompt = module_prompts.get(module, default_prompt)
    print(f"{prompt}\n\n---\n")
    return prompt


def merge_communication(query, documents, max_documents=5, max_length=4000, module="general"):
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
    return build_prompt(query, document_contents, module)


class Generator:
    def __init__(self):
        self.generate_model = GeneratorModel()

    def generate(self, query: str, res: List[Dict[str, Any]], module: str = "general"):
        merge_result = merge_communication(query, res, module=module)
        try:
            _, content = self.generate_model.communicate(merge_result)
            return content
        except Exception:
            return self._fallback_generate(query=query, docs=res, module=module)

    @staticmethod
    def _fallback_generate(query: str, docs: List[Dict[str, Any]], module: str = "general") -> str:
        snippets: List[str] = []
        for doc in (docs or [])[:3]:
            content = str(doc.get("content", "")).strip()
            if content:
                snippets.append(content[:180])
        if snippets:
            joined = "\n".join(f"- {s}" for s in snippets)
            return (
                f"离线模式回答（{module}）：\n"
                f"问题：{query}\n"
                "基于可用资料的要点：\n"
                f"{joined}"
            )
        return f"离线模式回答（{module}）：当前没有可用检索资料，建议补充上下文后重试。问题：{query}"
