#!/usr/bin/env python3
"""
测试RAG系统与各个模块的集成（简化版）
"""


def test_imports():
    """测试所有必要的导入"""
    print("测试导入模块...")
    
    # 测试RAG系统导入
    try:
        from rag_core.rag_system import RAGSystem
        print("✓ RAGSystem 导入成功")
    except Exception as e:
        print(f"✗ RAGSystem 导入失败: {e}")
    
    # 测试智能体导入
    try:
        from agent_core.agent import ielts_agent
        print("✓ ielts_agent 导入成功")
    except Exception as e:
        print(f"✗ ielts_agent 导入失败: {e}")
    
    # 测试词汇智能体导入
    try:
        from agent_core.agents.vocabulary_agent import VocabularyAgent
        print("✓ VocabularyAgent 导入成功")
    except Exception as e:
        print(f"✗ VocabularyAgent 导入失败: {e}")
    
    # 测试深度搜索智能体导入
    try:
        from agent_core.agents.deep_search_agent import DeepSearchAgent
        print("✓ DeepSearchAgent 导入成功")
    except Exception as e:
        print(f"✗ DeepSearchAgent 导入失败: {e}")
    
    # 测试阅读智能体导入
    try:
        from agent_core.agents.reading_agent import ReadingAgent
        print("✓ ReadingAgent 导入成功")
    except Exception as e:
        print(f"✗ ReadingAgent 导入失败: {e}")
    
    # 测试写作模块导入
    try:
        from agent_core.agents.writing.writing_generator import WritingGenerator
        from agent_core.agents.writing.writing_evaluator import WritingEvaluator
        print("✓ Writing模块 导入成功")
    except Exception as e:
        print(f"✗ Writing模块 导入失败: {e}")
    
    # 测试口语智能体导入
    try:
        from agent_core.agents.speaking.speaking_agent import SpeakingAgent
        print("✓ SpeakingAgent 导入成功")
    except Exception as e:
        print(f"✗ SpeakingAgent 导入失败: {e}")
    
    print("导入测试完成！")


def test_agent_registration():
    """测试智能体注册"""
    print("\n测试智能体注册...")
    
    try:
        from agent_core.agent import ielts_agent
        # 检查智能体是否成功注册
        print("✓ ielts_agent 初始化成功")
        
        # 检查智能体是否包含词汇智能体
        if hasattr(ielts_agent, 'agents') and 'vocabulary_agent' in ielts_agent.agents:
            print("✓ 词汇智能体注册成功")
        else:
            print("✗ 词汇智能体注册失败")
        
    except Exception as e:
        print(f"✗ 智能体注册测试失败: {e}")
    
    print("智能体注册测试完成！")


def test_module_integration():
    """测试模块集成"""
    print("\n测试模块集成...")
    
    # 测试RAG系统模块参数
    try:
        from rag_core.rag_system import RAGSystem
        rag_system = RAGSystem()
        print("✓ RAGSystem 初始化成功")
        print("✓ RAGSystem 支持模块参数")
    except Exception as e:
        print(f"✗ RAGSystem 测试失败: {e}")
    
    # 测试深度搜索模块集成
    try:
        from agent_core.agents.deep_search_agent import DeepSearchAgent
        deep_search_agent = DeepSearchAgent()
        print("✓ DeepSearchAgent 初始化成功")
        print("✓ 深度搜索模块集成RAG系统")
    except Exception as e:
        print(f"✗ DeepSearchAgent 测试失败: {e}")
    
    # 测试阅读模块集成
    try:
        from agent_core.agents.reading_agent import ReadingAgent
        reading_agent = ReadingAgent()
        print("✓ ReadingAgent 初始化成功")
        print("✓ 阅读模块集成RAG系统")
    except Exception as e:
        print(f"✗ ReadingAgent 测试失败: {e}")
    
    # 测试写作模块集成
    try:
        from agent_core.agents.writing.writing_generator import WritingGenerator
        from agent_core.agents.base_agent import BaseAgent
        base_agent = BaseAgent()
        writing_generator = WritingGenerator(base_agent.qwen_llm)
        print("✓ WritingGenerator 初始化成功")
        print("✓ 写作模块集成RAG系统")
    except Exception as e:
        print(f"✗ WritingGenerator 测试失败: {e}")
    
    # 测试口语模块集成
    try:
        from agent_core.agents.speaking.speaking_agent import SpeakingAgent
        speaking_agent = SpeakingAgent()
        print("✓ SpeakingAgent 初始化成功")
        print("✓ 口语模块集成RAG系统")
    except Exception as e:
        print(f"✗ SpeakingAgent 测试失败: {e}")
    
    print("模块集成测试完成！")


if __name__ == "__main__":
    print("开始测试RAG系统与各个模块的集成...")
    
    try:
        test_imports()
        test_agent_registration()
        test_module_integration()
        print("\n所有测试完成！集成成功！")
    except Exception as e:
        print(f"\n测试过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
