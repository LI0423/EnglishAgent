#!/usr/bin/env python3
# 测试智能体路由和处理链路

from agent_core.agent import ielts_agent

def test_agent_router():
    """测试智能体路由功能"""
    test_cases = [
        # 测试翻译智能体
        ("请帮我生成一个翻译题目", "translation_agent"),
        # 测试规划智能体
        ("请帮我生成一个个性化学习计划", "planning_agent"),
        # 测试口语智能体
        ("请评估我的口语回答：I think English is very important for my future", "speaking_agent"),
        # 测试写作智能体
        ("请帮我写一篇关于环境保护的范文", "writing_agent"),
        # 测试阅读智能体
        ("请分析这篇文章：The Internet has changed our lives in many ways", "reading_agent"),
        # 测试听力智能体
        ("{\"transcript\": \"Hello everyone, today we will talk about environmental protection\", \"questions\": [{\"id\": 1, \"student_answer\": \"environmental protection\", \"correct_answer\": \"environmental protection\", \"expected_answer_type\": \"topic\"}]}", "listening_agent"),
        # 测试通用智能体（回退）
        ("今天天气怎么样", "common_agent"),
    ]

    print("开始测试智能体路由和处理链路...\n")

    for query, expected_agent in test_cases:
        print(f"测试查询: {query}")
        print(f"期望智能体: {expected_agent}")
        
        try:
            # 使用CommonAgent处理查询
            result = ielts_agent.route_and_execute(query, "test_session_123")
            
            print(f"实际智能体: {result['agent']}")
            print(f"响应内容: {result['response'][:100]}...")  # 只显示前100个字符
            print(f"路由信息: {result['routing']}")
            
            # 检查是否路由到了正确的智能体
            if result['agent'] == expected_agent or (expected_agent == "common_agent" and result['agent'] == "common_agent"):
                print("✅ 测试通过: 路由到了正确的智能体")
            else:
                print("❌ 测试失败: 路由到了错误的智能体")
                
        except Exception as e:
            print(f"❌ 测试失败: {str(e)}")
        
        print("-" * 80)

if __name__ == "__main__":
    test_agent_router()
