from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

from agent_core.agents.base_agent import BaseAgent

class PlanningAgent(BaseAgent):
    """个性化学习计划智能体"""
    agent_key = "planning"
    
    def __init__(self, temperature: float = 0.0, enable_thinking: bool = False, use_streamer: bool = False):
        super().__init__(temperature, enable_thinking, use_streamer)
    
    def generate_personalized_plan(self, user_profile: Dict[str, Any], assessment_results: Dict[str, Any] = None) -> Dict[str, Any]:
        """生成个性化学习计划"""
        # 计算备考时间（如果有考试日期）
        user_id = user_profile.get("user_id", "unknown_user")
        target_score = user_profile.get("target_score")
        current_score = user_profile.get("current_score")
        weekly_hours = user_profile.get("study_hours_per_week") or 8
        availability = user_profile.get("availability", {"days_per_week": 7})
        days_per_week = availability.get("days_per_week", 7)

        weeks_left = self._weeks_until_exam(user_profile.get("exam_date"))
        duration_weeks = self._determine_duration_weeks(weeks_left)

        aggregated_weaknesses = self._aggregate_weaknesses(user_profile.get("weaknesses", []), assessment_results)
        main_weaknesses = [w for w, _ in aggregated_weaknesses][:3]

        goals = self._build_goals(main_weaknesses, current_score, target_score, duration_weeks)

        weekly_plans = self._build_weekly_plans(duration_weeks, main_weaknesses, weekly_hours)

        module_specific = self._build_module_specific(main_weaknesses)

        daily_schedule = self._build_daily_schedule(weekly_hours, days_per_week)

        review_plan = self._build_review_plan(duration_weeks)

        resources = self._build_resources()

        progress_tracking = [
            "记录每次练习的完成时长与正确率",
            "每周固定时间复盘错题",
            "在每次 checkpoint 后写下 3 条改进要点"
        ]

        plan_id = f"plan_{user_id}_{datetime.now(timezone.utc).strftime('%Y%m%dT%H%M%SZ')}"
        plan = {
            "plan_id": plan_id,
            "user_id": user_id,
            "start_date": datetime.now().date().isoformat(),
            "duration_weeks": duration_weeks,
            "overall_strategy": self._compose_overall_strategy(main_weaknesses, duration_weeks, weekly_hours, target_score),
            "goals": goals,
            "weekly_plans": weekly_plans,
            "module_specific": module_specific,
            "daily_schedule": daily_schedule,
            "review_plan": review_plan,
            "resources": resources,
            "progress_tracking": progress_tracking,
            "meta": {
                "priority": "high" if main_weaknesses else "normal",
                "confidence": self._estimate_confidence(assessment_results)
            }
        }

        return plan
    
    
    def update_personalized_plan(self, original_plan: Dict[str, Any], progress: Dict[str, Any], new_assessment: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        根据学习进度和新的评估结果更新个性化学习计划
        progress 示例：
          {
            "completed_tasks": ["t1","t2",...],
            "day_stats": {"day1": {"duration_min": 30, "completed": true}, ...},
            "checkpoint_results": {"week1": {"listening_accuracy": 0.7, ...}}
          }
        new_assessment: optional 各 agent 最新评估结果
        返回更新后的计划（结构同 generate_personalized_plan）
        """
        # 复制原计划（浅拷贝即可按需修改）
        plan = dict(original_plan)
        duration_weeks = plan.get("duration_weeks", 4)

        # 计算完成率（按 completed_tasks 与 weekly_plans 量化）
        completed = progress.get("completed_tasks", [])
        total_tasks_est = sum(len(w.get("tasks", [])) for w in plan.get("weekly_plans", [])) or 1
        completion_rate = min(1.0, len(completed) / total_tasks_est)

        # 若提供 new_assessment，重新聚合弱点
        if new_assessment:
            aggregated_weaknesses = self._aggregate_weaknesses(plan.get("module_specific", {}).get("weaknesses", []), new_assessment)
            new_main = [w for w, _ in aggregated_weaknesses][:3]
        else:
            # 若无新评估，根据完成率和原弱点决定是否降低负荷
            new_main = [w for w, _ in self._aggregate_weaknesses(None, None)][:3] if completion_rate > 0.9 else []
            # fallback to existing plan weaknesses if empty
            if not new_main:
                # try to extract from existing weekly_plans focus
                focuses = [w.get("focus", "") for w in plan.get("weekly_plans", [])]
                new_main = [f for f in focuses if f][:3]

        # 自适应策略：
        # 如果完成率低，降低未来每周任务量 20%，并把任务拆成短时段
        if completion_rate < 0.6:
            # 调整 daily schedule：减少每周小时
            old_hours = sum(slot.get("duration_min", 0) for slot in plan.get("daily_schedule", [])) / 60.0 if plan.get("daily_schedule") else 0
            reduce_hours = max(1, int(old_hours * 0.2))
            # 简单调整：在每个日程项末尾标注“（减量）”
            for slot in plan.get("daily_schedule", []):
                slot["activity"] = slot["activity"] + "（减量）"
            plan["meta"]["note"] = f"发现完成率较低（{completion_rate:.2f}），已自动降低任务强度。"

        # 如果 checkpoint 表现提升，减少该技能的未来练习权重
        checkpoint = progress.get("checkpoint_results", {})
        if checkpoint:
            improvements = []
            for ck, result in checkpoint.items():
                # 简单规则：若某项 score 提升 >= 0.1，则视为改进
                for k, v in result.items():
                    if isinstance(v, (int, float)) and v >= 0.1:
                        improvements.append(k)
            if improvements:
                plan["meta"]["note"] = plan["meta"].get("note", "") + f" 检测到提升: {improvements}。"

        # 如果有 new_assessment 且显示新的弱点，更新 weekly_plans 的 focus（简单替换）
        if new_assessment:
            extracted = self._extract_weaknesses_from_assessment(new_assessment)
            if extracted:
                # 重新生成 remaining weeks 的 weekly_plans focusing on new weaknesses
                remaining_weeks = max(1, duration_weeks - len(progress.get("completed_tasks", [])) // 3)
                new_weekly = self._build_weekly_plans(remaining_weeks, extracted[:3], plan.get("meta", {}).get("confidence", 0.5))
                plan["weekly_plans"] = plan.get("weekly_plans", [])[:max(0, duration_weeks - remaining_weeks)] + new_weekly
                plan["meta"]["note"] = plan["meta"].get("note", "") + " 根据新评估调整后半段计划。"

        # 更新计划修改时间
        plan["meta"]["updated_at"] = datetime.now().isoformat()
        return plan
    
    def _weeks_until_exam(self, exam_date_str: Optional[str]) -> Optional[int]:
        if not exam_date_str:
            return None
        try:
            exam_date = datetime.strptime(exam_date_str, "%Y-%m-%d").date()
            today = datetime.now().date()
            delta_days = (exam_date - today).days
            if delta_days <= 0:
                return 0
            return max(0, delta_days // 7)
        except Exception:
            return None
        
    def _determine_duration_weeks(self, weeks_left: Optional[int]) -> int:
        """
        决策备考周期：优先取 weeks_left（若合理），否则默认 4 周；限制在 4-12 周
        """
        if weeks_left is None or weeks_left <= 0:
            return 4
        return min(max(4, weeks_left), 12)

    def _aggregate_weaknesses(self, profile_weaknesses: Optional[List[str]], assessment_results: Optional[Dict[str, Any]]) -> List[tuple]:
        """
        将 profile 与各 agent 的 assessment 进行合并并排序，返回 list of (weakness, score)
        score 越高代表优先级越高（简单统计频率）
        """
        counter: Dict[str, int] = {}
        if profile_weaknesses:
            for w in profile_weaknesses:
                counter[w] = counter.get(w, 0) + 2  # 给 profile 中的弱点更高初始权重

        if assessment_results:
            # assessment_results 可能包含 per-agent keys with 'weaknesses' lists
            for agent_name, rep in assessment_results.items():
                if not isinstance(rep, dict):
                    continue
                # common places where weaknesses may live
                cand = rep.get("weaknesses") or rep.get("section_summary", {}).get("weaknesses") or rep.get("module_specific") or []
                if isinstance(cand, list):
                    for w in cand:
                        counter[w] = counter.get(w, 0) + 1
                # also check actionItems for types
                for item in rep.get("actionItems", []) if rep.get("actionItems") else []:
                    t = item.get("type")
                    if t:
                        counter[t] = counter.get(t, 0) + 1

        # fallback: if empty, return an empty list
        if not counter:
            return []

        # return sorted list of (weakness, score desc)
        return sorted(counter.items(), key=lambda x: x[1], reverse=True)

    def _build_goals(self, main_weaknesses: List[str], current_score: Any, target_score: Any, duration_weeks: int) -> List[Dict[str, Any]]:
        goals = []
        # overall goal
        if target_score and isinstance(target_score, (int, float)) and current_score and isinstance(current_score, (int, float)):
            goals.append({
                "goal_id": "g_overall",
                "skill": "overall",
                "baseline": current_score,
                "target": target_score,
                "deadline": (datetime.now().date() + timedelta(weeks=duration_weeks)).isoformat()
            })
        # per weakness goals
        for i, w in enumerate(main_weaknesses):
            goals.append({
                "goal_id": f"g_{i+1}",
                "skill": w,
                "baseline": None,
                "target": "improve",
                "deadline": (datetime.now().date() + timedelta(weeks=duration_weeks)).isoformat()
            })
        return goals

    def _build_weekly_plans(self, duration_weeks: int, main_weaknesses: List[str], weekly_hours: float) -> List[Dict[str, Any]]:
        """
        生成每周计划：每周设定一个 focus（按 main_weaknesses 轮替或集中）
        """
        plans = []
        # tasks templates map (skill -> sample tasks)
        task_templates = {
            "listening": [
                "数字听写训练 20min（30 条）",
                "同义替换精听 25min（3 段）",
                "Section 限时训练 30min（计时）"
            ],
            "reading": [
                "快速阅读与定位练习 30min（1 篇）",
                "细节题专项训练 25min（2 篇）",
                "长难句解析 20min"
            ],
            "writing": [
                "Task1 模板与范文学习 30min",
                "Task2 练习与点评 45min",
                "句式替换与词汇替换 25min"
            ],
            "speaking": [
                "Part2 口语卡片练习（录音）20min",
                "连贯性训练（话题扩展）20min",
                "发音与重音练习 15min"
            ],
            "translation": [
                "中译英 句子练习 20min",
                "英译中 句子对照 20min"
            ]
        }

        # choose focus per week: cycle through main weaknesses or default by skill tags
        for w in range(duration_weeks):
            if main_weaknesses:
                focus = main_weaknesses[w % len(main_weaknesses)]
            else:
                # rotate skills
                keys = list(task_templates.keys())
                focus = keys[w % len(keys)]
            # pick tasks relevant to focus
            tasks = []
            if focus in task_templates:
                tasks = task_templates[focus][:3]
            else:
                # generic mixed tasks
                tasks = [task for tpl in task_templates.values() for task in tpl][:3]

            plans.append({
                "week": w + 1,
                "focus": focus,
                "tasks": tasks
            })
        return plans

    def _build_module_specific(self, main_weaknesses: List[str]) -> Dict[str, List[str]]:
        """
        返回每个模块的针对性训练建议（基于主弱点给出更具体的建议）
        """
        base = {
            "listening": [
                "每天进行30分钟精听练习",
                "练习数字和细节捕捉",
                "听不同口音的材料"
            ],
            "reading": [
                "每天完成1篇阅读练习",
                "训练同义替换识别与定位关键词",
                "练习限时阅读"
            ],
            "writing": [
                "每周至少完成2篇 Task1/1篇 Task2",
                "学习高分范文并仿写",
                "句式与词汇替换训练"
            ],
            "speaking": [
                "每天进行15分钟口语练习并录音回听",
                "练习 Part2 长段练习和即兴回答",
                "听力转述与同义表达训练"
            ],
            "translation": [
                "双向句子翻译练习（中译英/英译中）",
                "学习常见习语和搭配"
            ]
        }

        # 对于识别到的主弱点，插入更具体的建议
        for mw in main_weaknesses:
            if "numeric" in mw or "number" in mw:
                base["listening"].insert(0, "每日 10 分钟数字听写专项")
            if "paraphrase" in mw or "synonym" in mw:
                base["reading"].insert(0, "句子同义替换辨识练习")
                base["listening"].insert(0, "同义替换辨识训练")
            if "grammar" in mw:
                base["writing"].insert(0, "句法与时态专项练习")
                base["speaking"].insert(0, "复杂句造句练习")
            if "pronunciation" in mw or "pron" in mw:
                base["speaking"].insert(0, "发音重音与连读专项训练")

        return base

    def _build_daily_schedule(self, weekly_hours: float, days_per_week: int) -> List[Dict[str, Any]]:
        """
        构建示例日程：将 weekly_hours 分配到 days_per_week，并以块状时间返回
        """
        if days_per_week <= 0:
            days_per_week = 7
        minutes_per_day = int((weekly_hours * 60) / days_per_week)
        # split into 2 blocks per day (morning, evening) where possible
        morning = max(10, minutes_per_day // 2)
        evening = max(10, minutes_per_day - morning)
        schedule = [
            {"time_slot": "08:00-08:30", "activity": f"词汇/准备（{morning} min）", "duration_min": morning},
            {"time_slot": "19:00-19:30", "activity": f"专项练习（{evening} min）", "duration_min": evening}
        ]
        return schedule

    def _build_review_plan(self, duration_weeks: int) -> List[str]:
        # 安排 weekly review 和 mid/end checkpoints
        rp = ["每周日进行一次错题复盘与进度总结"]
        mid = max(1, duration_weeks // 2)
        rp.append(f"第{mid}周进行一次中期模拟（包含听力+阅读+写作+口语）并生成 checkpoint 报告")
        rp.append(f"第{duration_weeks}周进行一次完整模考并评估进步")
        return rp

    def _build_resources(self) -> List[Dict[str, str]]:
        return [
            {"type": "词汇", "name": "雅思核心词汇表", "description": "高频词与短语，分级记忆"},
            {"type": "真题", "name": "剑桥雅思真题集", "description": "包含历年完整真题与听力材料"},
            {"type": "听力练习", "name": "核心听力训练包", "description": "按题型划分的听力训练素材"},
            {"type": "写作", "name": "高分范文与批改", "description": "范文拆解+写作任务练习"},
            {"type": "口语", "name": "口语题库与模版", "description": "话题库与示范答案"}
        ]

    def _compose_overall_strategy(self, main_weaknesses: List[str], duration_weeks: int, weekly_hours: float, target_score: Any) -> str:
        strategy = "模块化训练为主，重点突破薄弱项；结合定期模考进行成果检验。"
        if main_weaknesses:
            strategy = f"优先攻克：{', '.join(main_weaknesses)}。每周保持 {weekly_hours} 小时学习，总周期 {duration_weeks} 周。"
        if target_score:
            strategy += f" 目标：在周期内向 {target_score} 靠拢。"
        return strategy

    def _estimate_confidence(self, assessment_results: Optional[Dict[str, Any]]) -> float:
        # 简单启发式：如果有多源评估，confidence 更高
        if not assessment_results:
            return 0.5
        count = len([k for k, v in assessment_results.items() if v])
        return min(0.9, 0.5 + 0.1 * count)

    def _extract_weaknesses_from_assessment(self, new_assessment: Dict[str, Any]) -> List[str]:
        # 把 new_assessment 各 agent 的 weakness 合并为一个 list（去重）
        out = set()
        if not new_assessment:
            return []
        for agent_name, rep in new_assessment.items():
            if not isinstance(rep, dict):
                continue
            cand = rep.get("weaknesses") or rep.get("section_summary", {}).get("weaknesses") or []
            if isinstance(cand, list):
                for w in cand:
                    out.add(w)
        return list(out)

    def generate_response(self, query: str, history: list) -> str:
        """生成个性化学习计划响应"""
        self.before_run(query, history)
        
        # 假设 query 格式："生成学习计划：{user_profile_json}"
        try:
            # 尝试从查询中提取用户信息
            import json
            user_profile = json.loads(query.replace("生成学习计划：", "").strip())
        except Exception:
            # 如果解析失败，使用默认用户信息
            user_profile = {
                "user_id": "test_user",
                "target_score": 7.0,
                "current_score": 6.0,
                "study_hours_per_week": 10,
                "availability": {"days_per_week": 5},
                "weaknesses": ["listening", "writing"]
            }
        
        result = self.generate_personalized_plan(user_profile)
        return self.after_run(self.format_plan(result))

    def format_plan(self, plan: Dict[str, Any]) -> str:
        """格式化学习计划输出"""
        lines = [
            "【个性化学习计划】",
            f"计划ID: {plan.get('plan_id', '')}",
            f"开始日期: {plan.get('start_date', '')}",
            f"持续时间: {plan.get('duration_weeks', 0)}周",
            f"整体策略: {plan.get('overall_strategy', '')}",
            "",
            "【目标】",
        ]
        
        for goal in plan.get('goals', []):
            lines.append(f"- {goal.get('skill', '')}: 从 {goal.get('baseline', '')} 到 {goal.get('target', '')}")
        
        lines.extend([
            "",
            "【每周计划】",
        ])
        
        for weekly in plan.get('weekly_plans', []):
            lines.append(f"第{weekly.get('week', 0)}周: {weekly.get('focus', '')}")
            for task in weekly.get('tasks', []):
                lines.append(f"  - {task}")
        
        lines.extend([
            "",
            "【每日安排】",
        ])
        
        for slot in plan.get('daily_schedule', []):
            lines.append(f"{slot.get('time_slot', '')}: {slot.get('activity', '')} ({slot.get('duration_min', 0)}分钟)")
        
        lines.extend([
            "",
            "【复习计划】",
        ])
        
        for item in plan.get('review_plan', []):
            lines.append(f"- {item}")
        
        return "\n".join(lines)
