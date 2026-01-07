
import json
import re
from typing import Any, Dict, List, Optional, Tuple

from agent_core.agents.base_agent import BaseAgent


class ListeningAgent(BaseAgent):
    """听力智能体"""
    agent_key: str = "listening"

    def __init__(self, temperature: float = 0.0, enable_thinking: bool = False, use_streamer: bool = False):
        super().__init__(temperature, enable_thinking, use_streamer)

        self.spelling_threshold = 0.25
        self.weak_overlap_threshold = 0.35
        # 常见月份/序数映射（用于简单数字/日期标准化）
        self._ord_map = {
            "first": "1", "second": "2", "third": "3", "fourth": "4", "fifth": "5",
            "sixth": "6", "seventh": "7", "eighth": "8", "ninth": "9", "tenth": "10",
            "eleventh": "11", "twelfth": "12", "thirteenth": "13", "fourteenth": "14", "fifteenth": "15",
            "sixteenth": "16", "seventeenth": "17", "eighteenth": "18", "nineteenth": "19", "twentieth": "20",
            "thirtieth": "30", "twenty": "20"
        }

    def can_handle(self, query: str) -> bool:
        return any(k in query for k in ("听力", "listening", "雅思听力"))
    
    def generate_response(self, query, history):
        self.before_run(query, history)

        payload = self._try_parse_json(query)
        if payload is None:
            return self.fallback()
        
        report = self.process_payload(payload)
        return self.after_run(self._format_report(report))
    
    def process_payload(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        transcript = payload.get("transcript", "")
        if not transcript:
            return {"error": "缺少transcript，请先运行ASR并传入transcript字段。"}
        
        questions = payload.get("questions", [])
        section = payload.get("section", None)

        per_question_results = []
        for q in questions:
            qid = q.get("id")
            student = q.get("student_answer", "")
            correct = q.get("correct_answer", "")
            expected_type = q.get("expected_answer_type", "")
            time_hint = q.get("time_hint")
            qtype = q.get("type", "unknown")

            correct_flag, error_type, confidence, evidence = self._rule_judge(student, correct, expected_type, transcript)

            if confidence < 0.6:
                llm_decision = self._llm_refine_error(student, correct, evidence, transcript)
                if llm_decision:
                    correct_flag = llm_decision.get("correct", correct_flag)
                    error_type = llm_decision.get("error_type", error_type)
                    confidence = max(confidence, llm_decision.get("confidence", confidence))
                    evidence = evidence or llm_decision.get("evidence", "")

            time_range, span = self._find_time_range_for_answer(transcript, correct, time_hint)
            suggestion = self._suggest_for_error(error_type)

            per_question_results.append({
                "id": qid,
                "type": qtype,
                "student_answer": student,
                "correct_answer": correct,
                "correct": bool(correct_flag),
                "error_type": None if correct_flag else error_type,
                "confidence": round(float(confidence), 2),
                "time_range": time_range,
                "evidence": {
                    "transcript_span": span,
                    "student_text": student
                },
                "suggestion": suggestion
            })
        # 聚合
        overall_accuracy = sum(1 for r in per_question_results if r["correct"]) / len(per_question_results) if per_question_results else 0.0
        section_summary = self._aggregate_section(per_question_results, section)
        band_estimate = self._map_accuracy_to_band(overall_accuracy * (len(per_question_results) if per_question_results else 0))

        # highlights: 合并所有 time_range，扩展上下文 1.5s
        highlight_ranges = self._merge_highlight_ranges([r["time_range"] for r in per_question_results if r["time_range"]])

        # practice plan based on top weaknesses
        top_weaknesses = section_summary.get("weaknesses", [])
        practice_plan = self._generate_practice_plan(top_weaknesses)

        report = {
            "overall_accuracy": round(overall_accuracy, 3),
            "band_estimate": band_estimate,
            "per_question": per_question_results,
            "section_summary": section_summary,
            "tips": self._generate_general_tips(top_weaknesses),
            "practice_plan": practice_plan,
            "highlight_ranges": highlight_ranges,
            "raw": {
                "transcript": transcript
            }
        }
        return report

    def _rule_judge(self, student: str, correct: str, expected_type: str, transcript: str) -> Tuple[bool, str, float, str]:
        """
        返回： (correct_flag, error_type, confidence, evidence_text)
        confidence: 0.0 ~ 1.0 (规则判定尽量给出较高置信度，模糊情况给低置信度)
        """
        s = self._normalize(student)
        c = self._normalize(correct)

        # exact match
        if s and c and s == c:
            return True, "", 0.99, f"exact match '{s}'"

        # 数字/日期检测
        if self._is_numeric_answer(c) or self._is_numeric_answer(s) or expected_type in ("number", "date", "amount"):
            s_num = self._normalize_number(s)
            c_num = self._normalize_number(c)
            if s_num is not None and c_num is not None:
                if s_num == c_num:
                    return True, "", 0.98, f"numeric match {s_num}"
                else:
                    return False, "numeric_error", 0.9, f"student:{s_num} vs correct:{c_num}"
            # 若无法解析成数字，置信度较低
            return False, "numeric_error", 0.5, f"could not normalize numbers student:{s} correct:{c}"

        # 拼写错误（编辑距离）
        dist = self._levenshtein_distance(s, c)
        norm = dist / max(len(c), 1)
        if norm <= self.spelling_threshold:
            # 若词形上接近但不相等，认定为拼写错误
            return False, "spelling_error", 0.85, f"edit_distance={dist}"

        # 词汇重叠率（判断 paraphrase / partial）
        overlap = self._token_overlap_ratio(s, c)
        if overlap >= 0.6:
            # 词汇高度重叠但不等，可能拼写/小改动，置信度中等
            return False, "minor_difference", 0.7, f"overlap={overlap:.2f}"
        elif 0.2 < overlap < 0.6:
            # 可能 paraphrase（学生未捕捉同义或部分信息）
            return False, "paraphrase_miss", 0.55, f"overlap={overlap:.2f}"
        else:
            # 低重叠，可能定位错误或干扰项
            return False, "localization_or_distractor", 0.45, f"overlap={overlap:.2f}"

    def _llm_refine_error(self, student: str, correct: str, evidence: str, transcript: str) -> Optional[Dict[str, Any]]:
        """
        当规则置信度较低时，用 LLM 复核以提高准确性（仅在 self.qwen_llm 可用时执行）
        返回字典：{"correct": bool, "error_type": str, "confidence": float, "evidence": str}
        """
        # 如果没有 llm 可用，则返回 None
        if not getattr(self, "qwen_llm", None):
            return None

        prompt = (
            "你是一名雅思听力教练，帮我判断学生答案是否正确并指出错误类型。\n"
            f"正确答案：{correct}\n"
            f"学生答案：{student}\n"
            f"上下文 transcript（供参考）：{transcript[:1000]}\n\n"
            "如果正确返回: {\"correct\": true, \"error_type\": \"\", \"confidence\": 0.95, \"evidence\": \"...\"}\n"
            "如果不正确，从 [numeric_error, spelling_error, paraphrase_miss, localization_error, distractor_error, inference_error] 中选择一个 error_type，并返回 JSON。\n"
            "只输出 JSON。"
        )
        try:
            _, raw = self.qwen_llm.communicate(prompt)
            parsed = self._safe_extract_json(raw)
            if not parsed:
                return None
            # normalize fields
            return {
                "correct": bool(parsed.get("correct", False)),
                "error_type": parsed.get("error_type", parsed.get("type", None)),
                "confidence": float(parsed.get("confidence", 0.5)),
                "evidence": parsed.get("evidence", "")
            }
        except Exception:
            return None

    def _find_time_range_for_answer(self, transcript: str, correct_answer: str, time_hint: Optional[List[float]]) -> Tuple[Optional[List[float]], Optional[str]]:
        """
        如果提供 time_hint，直接返回；否则尝试在 transcript 中搜索包含正确答案的片段并返回 None time_range（无法准确定位）
        注意：如果你的 ASR 提供 segments/time stamps，应改为基于 segments 返回精确 time_range
        """
        if time_hint:
            return time_hint, self._extract_span_from_transcript(transcript, correct_answer)

        # 简单搜索 span（不含时间戳）
        span = self._extract_span_from_transcript(transcript, correct_answer)
        return None, span

    def _extract_span_from_transcript(self, transcript: str, phrase: str) -> Optional[str]:
        if not transcript or not phrase:
            return None
        idx = transcript.lower().find(phrase.lower())
        if idx >= 0:
            # return short window as evidence
            start = max(0, idx - 40)
            end = min(len(transcript), idx + len(phrase) + 40)
            return transcript[start:end].strip()
        return None

    # ---------------------------
    # 聚合与报告生成
    # ---------------------------
    def _aggregate_section(self, per_question_results: List[Dict[str, Any]], section: Optional[int]) -> Dict[str, Any]:
        total = len(per_question_results)
        if total == 0:
            return {"section": section, "accuracy": 0.0, "weaknesses": [], "counts": {}}

        correct_count = sum(1 for r in per_question_results if r["correct"])
        accuracy = correct_count / total

        # 统计错误类型分布
        counts: Dict[str, int] = {}
        for r in per_question_results:
            et = r.get("error_type") or "none"
            counts[et] = counts.get(et, 0) + 1

        # 排序找出 top weaknesses（排除 'none'）
        weakness_items = sorted(
            ((k, v) for k, v in counts.items() if k and k != "none"),
            key=lambda x: x[1], reverse=True
        )
        weaknesses = [k for k, _ in weakness_items[:3]]

        return {
            "section": section,
            "accuracy": round(accuracy, 3),
            "weaknesses": weaknesses,
            "counts": counts
        }

    def _map_accuracy_to_band(self, correct_count: int) -> float:
        """
        简单将正确题数（0-40）映射到 Band，近似经验表
        注意：如果你传入 overall_accuracy*total，确保 total=40 或调整逻辑
        """
        # If user didn't provide length 40 mapping, assume correct_count is already in 0-40
        c = int(round(correct_count))
        if c >= 39:
            return 9.0
        if c >= 37:
            return 8.0
        if c >= 34:
            return 7.5
        if c >= 31:
            return 7.0
        if c >= 28:
            return 6.5
        if c >= 23:
            return 6.0
        if c >= 18:
            return 5.5
        return 5.0

    def _merge_highlight_ranges(self, ranges: List[Optional[List[float]]]) -> List[List[float]]:
        """合并并扩展时间区间（若输入包含 None 则忽略）"""
        valid = [tuple(r) for r in ranges if r]
        if not valid:
            return []
        # sort
        valid = sorted(valid, key=lambda x: x[0])
        merged = []
        cur_s, cur_e = valid[0]
        for s, e in valid[1:]:
            if s <= cur_e + 0.5:
                cur_e = max(cur_e, e)
            else:
                merged.append([max(0, cur_s - 1.5), cur_e + 1.5])
                cur_s, cur_e = s, e
        merged.append([max(0, cur_s - 1.5), cur_e + 1.5])
        return merged

    # ---------------------------
    # 练习建议生成（模板化）
    # ---------------------------
    def _suggest_for_error(self, error_type: str) -> str:
        mapping = {
            "numeric_error": "数字听写训练：练习日期、金额和序数词听写。",
            "spelling_error": "拼写注意：练习单词听写并核对拼写，复习常见容易错词。",
            "paraphrase_miss": "同义替换训练：练习将句子改写为多种表达，积累常见替换。",
            "localization_or_distractor": "定位与排除干扰项训练：练习先读题再定位关键词并标记上下文。",
            "minor_difference": "细节检查：注意冠词、单复数和小词的差别。",
            None: "复习基础答题技巧：先读题带关键字再听取答案区域。"
        }
        return mapping.get(error_type, "针对性练习：复习相关题型并做 15–20 道专项题。")

    def _generate_practice_plan(self, weaknesses: List[str]) -> List[Dict[str, Any]]:
        """
        根据 weaknesses 生成 7 天的练习计划（模板化）
        """
        plan = []
        # base templates
        for day in range(1, 8):
            if not weaknesses:
                task = "综合真题模拟 1 套（计时），并逐题分析"
                duration = 30
            else:
                primary = weaknesses[0]
                if primary == "numeric_error":
                    task = "数字听写与序数词练习（包含 30 个数字/日期）"
                    duration = 20
                elif primary == "spelling_error":
                    task = "高频错误词听写与拼写检查练习"
                    duration = 20
                elif primary == "paraphrase_miss":
                    task = "同义替换辨识与改写练习"
                    duration = 25
                else:
                    task = "定位+同义替换练习（按题型做 20 道）"
                    duration = 25
            plan.append({"day": day, "task": task, "duration_min": duration})
        return plan

    def _generate_general_tips(self, weaknesses: List[str]) -> List[str]:
        tips = [
            "答题前先快速浏览问题并圈关键词。",
            "在听到数字和专有名词时重点记录音素与上下文。",
            "遇到不确定选项时，先标记，听完整段落再回填。"
        ]
        if "numeric_error" in weaknesses:
            tips.insert(0, "加强数字、序数词与日期的听写练习。")
        if "paraphrase_miss" in weaknesses:
            tips.insert(0, "练习同义替换识别，积累常见替换表达。")
        return tips

    # ---------------------------
    # 工具函数
    # ---------------------------
    def _normalize(self, text: str) -> str:
        if not text:
            return ""
        text = text.lower().strip()
        # remove punctuation except digits and % and - for ranges
        text = re.sub(r"[^\w\s%\-']", " ", text)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    def _is_numeric_answer(self, text: str) -> bool:
        if not text:
            return False
        if re.search(r"\d", text):
            return True
        # months or ordinals
        months = ("january february march april may june july august september october november december")
        if any(m in text.lower() for m in months.split()):
            return True
        if any(ordw in text.lower() for ordw in ("first second third fourth fifth sixth seventh eighth ninth tenth",)):
            return True
        return False

    def _normalize_number(self, text: str) -> Optional[int]:
        """
        尝试把数字/序数/日期文本转成 int（尽量覆盖常见场景）
        返回 None 表示无法解析
        """
        if not text:
            return None
        t = text.lower()
        # direct digits
        m = re.search(r"-?\d+", t)
        if m:
            try:
                return int(m.group())
            except Exception:
                pass
        # ordinals like 'fifteenth' or 'fifteen'
        # try mapping common words
        # split and find one token that maps to known ord_map or numeric word
        tokens = re.findall(r"[a-z]+", t)
        for tok in tokens:
            if tok in self._ord_map:
                try:
                    return int(self._ord_map[tok])
                except Exception:
                    pass
            # spelled-out numbers 1-20 common words
            small_map = {
                "one": 1, "two": 2, "three": 3, "four": 4, "five": 5,
                "six": 6, "seven": 7, "eight": 8, "nine": 9, "ten": 10,
                "eleven": 11, "twelve": 12, "thirteen": 13, "fourteen": 14,
                "fifteen": 15, "sixteen": 16, "seventeen": 17, "eighteen": 18,
                "nineteen": 19, "twenty": 20, "thirty": 30, "forty": 40
            }
            if tok in small_map:
                return small_map[tok]
        return None

    def _levenshtein_distance(self, a: str, b: str) -> int:
        # classic DP
        if a == b:
            return 0
        la, lb = len(a), len(b)
        if la == 0:
            return lb
        if lb == 0:
            return la
        prev = list(range(lb + 1))
        for i, ca in enumerate(a, start=1):
            cur = [i] + [0] * lb
            for j, cb in enumerate(b, start=1):
                cost = 0 if ca == cb else 1
                cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + cost)
            prev = cur
        return prev[lb]

    def _token_overlap_ratio(self, s: str, c: str) -> float:
        s_tokens = set(s.split())
        c_tokens = set(c.split())
        if not c_tokens:
            return 0.0
        return len(s_tokens & c_tokens) / len(c_tokens)

    def _try_parse_json(self, text: str) -> Optional[Dict[str, Any]]:
        try:
            return json.loads(text)
        except Exception:
            return None

    def _safe_extract_json(self, text: str) -> Optional[Dict[str, Any]]:
        """
        尝试从 LLM 原始输出中提取第一段 JSON 对象
        """
        if not text:
            return None
        # remove triple backticks
        text = re.sub(r"```.*?```", "", text, flags=re.DOTALL)
        # find first {...}
        m = re.search(r"\{[\s\S]*\}", text)
        if not m:
            return None
        try:
            return json.loads(m.group())
        except Exception:
            return None

    # ---------------------------
    # 输出格式化（供 human-readable 展示）
    # ---------------------------
    def _format_report(self, report: Dict[str, Any]) -> str:
        if "error" in report:
            return report["error"]
        lines = []
        lines.append("【听力诊断报告】")
        lines.append(f"整体准确率: {report['overall_accuracy']*100:.1f}%")
        lines.append(f"Band 估算: {report['band_estimate']}")
        lines.append("\n-- 每题详情 --")
        for pq in report["per_question"]:
            lines.append(f"题目 {pq['id']} ({pq['type']}): {'正确' if pq['correct'] else '错误'}")
            if not pq["correct"]:
                lines.append(f"  错误类型: {pq['error_type']} (置信度 {pq['confidence']})")
                if pq["time_range"]:
                    lines.append(f"  时间区间: {pq['time_range']}")
                if pq["evidence"]["transcript_span"]:
                    lines.append(f"  证据片段: {pq['evidence']['transcript_span']}")
                lines.append(f"  建议: {pq['suggestion']}")
        lines.append("\n-- 小结（Section） --")
        ss = report["section_summary"]
        lines.append(f"Section: {ss.get('section')}，准确率: {ss.get('accuracy')*100:.1f}%")
        lines.append(f"弱点: {', '.join(ss.get('weaknesses', []) )}")
        lines.append("\n-- 推荐练习计划（7 天） --")
        for d in report["practice_plan"]:
            lines.append(f"Day {d['day']}: {d['task']} ({d['duration_min']} min)")
        if report["highlight_ranges"]:
            lines.append("\n建议重听区间：")
            for s, e in report["highlight_ranges"]:
                lines.append(f"- {s:.1f}s ~ {e:.1f}s")
        return "\n".join(lines)
