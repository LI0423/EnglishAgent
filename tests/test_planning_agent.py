from agent_core import planning_agent

# 测试生成个性化学习计划
user_profile = {
    "target_score": 7.0,
    "current_score": 6.0,
    "study_hours_per_week": 15,
    "weaknesses": ["writing", "speaking"],
    "exam_date": "2025-01-30"
}

assessment_results = {
    "listening": 6.5,
    "reading": 6.5,
    "writing": 5.5,
    "speaking": 5.5,
    "overall": 6.0
}

print("测试生成个性化学习计划...")
plan = planning_agent.generate_personalized_plan(user_profile, assessment_results)
print("\n生成的学习计划:")
print(f"总体策略: {plan['overall_strategy']}")
print(f"\n每周计划数量: {len(plan['weekly_plans'])}")
print(f"\n模块针对性建议:")
for module, tips in plan['module_specific'].items():
    print(f"{module}: {tips[:2]}...")
print(f"\n每日安排: {plan['daily_schedule'][:3]}...")
print(f"\n资源推荐数量: {len(plan['resources'])}")
print(f"\n进步跟踪建议: {plan['progress_tracking'][:2]}...")

# 测试更新个性化学习计划
progress = {
    "completed_weeks": 2,
    "progress_rate": 0.5,
    "improvements": ["listening", "reading"],
    "remaining_weaknesses": ["writing"]
}

new_assessment = {
    "listening": 7.0,
    "reading": 7.0,
    "writing": 6.0,
    "speaking": 6.0,
    "overall": 6.5
}

print("\n\n测试更新个性化学习计划...")
updated_plan = planning_agent.update_personalized_plan(plan, progress, new_assessment)
print("\n更新后的学习计划:")
print(f"总体策略: {updated_plan['overall_strategy']}")
print(f"\n每周计划数量: {len(updated_plan['weekly_plans'])}")
print(f"\n模块针对性建议:")
for module, tips in updated_plan['module_specific'].items():
    print(f"{module}: {tips[:2]}...")

print("\n\n测试完成！")
