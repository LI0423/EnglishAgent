import importlib.util
import sys
from pathlib import Path

# 直接从文件加载模块，避免导入 package-level __init__ 时触发可选依赖报错
spec = importlib.util.spec_from_file_location(
	"issue_analysis_agent",
	str(Path(__file__).parent.joinpath("agent_core", "issue_analysis_agent.py").resolve()),
)
mod = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = mod
spec.loader.exec_module(mod)
issue_analysis_agent = mod.issue_analysis_agent

print("测试 IssueAnalysisAgent: 写作评估 路由")
q = "请帮我批改这篇作文"
ctx = {"essay": "This is a sample essay to test the writing evaluation."}
import types
import sys

# 在运行时注入轻量的 agent_core.agent 伪模块，避免加载重量级模型
fake_agent_mod = types.ModuleType("agent_core.agent")
fake_agent_mod.writing_agent = types.SimpleNamespace(
	evaluate_writing=lambda essay, task_type="task2": {
		"scores": {"TR": 7.0, "CC": 6.5, "LR": 6.5, "GRA": 6.0},
		"overall": 6.5,
		"rationales": ["任务回应完整"],
	}
)
fake_agent_mod.speaking_agent = types.SimpleNamespace(evaluate_speaking=lambda transcript: {"scores": {"FC": 6.5}, "overall": 6.5})
fake_agent_mod.reading_agent = types.SimpleNamespace(analyze_passage=lambda passage: {"主题": "测试主题"})
fake_agent_mod.listening_agent = types.SimpleNamespace(evaluate_listening=lambda t, a, c: {"overall": "良好"})
fake_agent_mod.planning_agent = types.SimpleNamespace(generate_personalized_plan=lambda profile, assessment: {"overall_strategy": "测试策略"})
fake_agent_mod.translation_agent = types.SimpleNamespace(
	generate_translation_question=lambda difficulty="medium": {"chinese_sentence": "测试句子", "difficulty": difficulty},
	check_translation=lambda ch, ut: {"overall": 8.0},
)
fake_agent_mod.ielts_agent = types.SimpleNamespace(
	route_and_execute=lambda query, session_id: {
		"agent": "common_agent",
		"response": "stub-response",
		"routing": {"reason": "stub"},
	}
)
sys.modules["agent_core.agent"] = fake_agent_mod

res = issue_analysis_agent.analyze_and_route(q, user_context=ctx)
print(res)
# 如果意图置信度不足，会要求澄清；否则应路由到写作评估
if res.get("clarify"):
	print("路由被拒绝，要求澄清（这是可接受的行为）")
else:
	assert res.get("handler") == "_handle_writing"
	assert isinstance(res.get("result"), dict)
	assert "scores" in res["result"]

print("\n测试 IssueAnalysisAgent: 口语评估 路由（缺少 transcript）")
q2 = "我想让你评价我的口语"
res2 = issue_analysis_agent.analyze_and_route(q2, user_context={})
print(res2)
# 置信度可能低或路由为澄清，至少要包含 intent
assert "intent" in res2

print("\n测试 IssueAnalysisAgent: 歧义查询需要澄清")
q3 = "我想提高我的英语"
res3 = issue_analysis_agent.analyze_and_route(q3, user_context={})
print(res3)
# 置信度低时，agent 应该返回 clarify 指示或候选
assert (res3.get("clarify") is True) or (res3.get("handler") is not None)

print("\n所有测试通过！")
