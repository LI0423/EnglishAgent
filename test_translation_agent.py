from agent_core import translation_agent

# 测试生成翻译题目
print("测试生成翻译题目...")
question = translation_agent.generate_translation_question(difficulty="medium")
print(f"\n生成的翻译题目:")
print(f"中文句子: {question['chinese_sentence']}")
print(f"难度: {question['difficulty']}")
print(f"主题: {question['topic']}")

# 测试检查翻译
user_translation = "As technology develops, people's lifestyle has changed greatly."
print(f"\n\n测试检查翻译...")
print(f"用户翻译: {user_translation}")
evaluation = translation_agent.check_translation(question['chinese_sentence'], user_translation)
print(f"\n翻译评价:")
print(f"准确性: {evaluation['accuracy']}/10")
print(f"流畅度: {evaluation['fluency']}/10")
print(f"语法: {evaluation['grammar']}/10")
print(f"词汇: {evaluation['vocabulary']}/10")
print(f"总分: {evaluation['overall']}/10")
print(f"评价: {evaluation['evaluation']}")
print(f"改进建议: {evaluation['suggestions']}")
print(f"参考翻译: {evaluation['correct_translation']}")

# 测试不同难度的题目生成
print("\n\n测试生成不同难度的翻译题目...")
easy_question = translation_agent.generate_translation_question(difficulty="easy")
hard_question = translation_agent.generate_translation_question(difficulty="hard")
print(f"简单题目: {easy_question['chinese_sentence']}")
print(f"困难题目: {hard_question['chinese_sentence']}")

print("\n\n测试完成！")
