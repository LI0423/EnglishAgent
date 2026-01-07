import pytest
import requests
import json
import time

# 测试配置
BASE_URL = "http://localhost:8000"
TEST_USER = {
    "phone": "13800138000",
    "password": "test_password"
}
TEST_USERNAME = "test_user"

# 辅助函数
def get_auth_token():
    """获取认证token"""
    response = requests.post(f"{BASE_URL}/auth/login", json={
        "phone": TEST_USER["phone"],
        "password": TEST_USER["password"]
    })
    return response.json()["token"]

class TestAuth:
    """测试认证模块"""
    
    def test_register_phone(self):
        """测试手机号注册"""
        response = requests.post(f"{BASE_URL}/auth/register/phone", json={
            "phone": TEST_USER["phone"],
            "password": TEST_USER["password"]
        })
        assert response.status_code in [200, 400]  # 可能已存在
        if response.status_code == 200:
            assert "success" in response.json()
            assert response.json()["success"] == True
    
    def test_login_phone(self):
        """测试手机号登录"""
        response = requests.post(f"{BASE_URL}/auth/login", json={
            "phone": TEST_USER["phone"],
            "password": TEST_USER["password"]
        })
        assert response.status_code == 200
        assert "token" in response.json()
        return response.json()["token"]
    
    def test_login_username(self):
        """测试用户名登录"""
        # 先注册用户名
        requests.post(f"{BASE_URL}/auth/register", json={
            "username": TEST_USERNAME,
            "password": TEST_USER["password"]
        })
        
        # 测试登录
        response = requests.post(f"{BASE_URL}/auth/login", json={
            "username": TEST_USERNAME,
            "password": TEST_USER["password"]
        })
        assert response.status_code == 200
        assert "token" in response.json()
        return response.json()["token"]
    
    def test_get_me(self):
        """测试获取当前用户信息"""
        token = self.test_login_phone()
        response = requests.get(f"{BASE_URL}/auth/me", headers={
            "Authorization": f"Bearer {token}"
        })
        assert response.status_code == 200
        assert "userId" in response.json()
        assert "username" in response.json()

class TestSpeaking:
    """测试口语模块"""
    
    def setup_method(self):
        """设置测试环境"""
        auth_test = TestAuth()
        self.token = auth_test.test_login_phone()
    
    def test_create_session(self):
        """测试创建口语会话"""
        response = requests.post(f"{BASE_URL}/speaking/session", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "sessionId" in response.json()
        assert "topic" in response.json()
        assert "parts" in response.json()
        return response.json()["sessionId"]
    
    def test_list_sessions(self):
        """测试获取会话列表"""
        response = requests.get(f"{BASE_URL}/speaking/sessions", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_session_detail(self):
        """测试获取会话详情"""
        session_id = self.test_create_session()
        response = requests.get(f"{BASE_URL}/speaking/session/{session_id}", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "id" in response.json()
        assert response.json()["id"] == session_id
    
    def test_start_part(self):
        """测试开始会话部分"""
        session_id = self.test_create_session()
        response = requests.post(f"{BASE_URL}/speaking/session/{session_id}/part/1/start", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "ok" in response.json()
        assert response.json()["ok"] == True
    
    def test_upload_audio(self):
        """测试上传音频"""
        session_id = self.test_create_session()
        response = requests.post(f"{BASE_URL}/speaking/session/{session_id}/audio", json={
            "textPartial": "This is a test audio transcription."
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "asrPartial" in response.json()
    
    def test_finish_session(self):
        """测试完成会话"""
        session_id = self.test_create_session()
        # 先上传音频
        requests.post(f"{BASE_URL}/speaking/session/{session_id}/audio", json={
            "textPartial": "This is a test audio transcription."
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        # 完成会话
        response = requests.post(f"{BASE_URL}/speaking/session/{session_id}/finish", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "transcriptId" in response.json()
        return response.json()["transcriptId"]

class TestScoring:
    """测试评分模块"""
    
    def setup_method(self):
        """设置测试环境"""
        auth_test = TestAuth()
        self.token = auth_test.test_login_phone()
        
        # 创建并完成一个会话
        speaking_test = TestSpeaking()
        speaking_test.setup_method()
        self.transcript_id = speaking_test.test_finish_session()
    
    def test_score_speaking(self):
        """测试口语评分"""
        response = requests.post(f"{BASE_URL}/scoring/speaking", json={
            "transcriptId": self.transcript_id
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "scores" in response.json()
        assert "overall" in response.json()

class TestReport:
    """测试报告模块"""
    
    def setup_method(self):
        """设置测试环境"""
        auth_test = TestAuth()
        self.token = auth_test.test_login_phone()
        
        # 创建一个会话
        speaking_test = TestSpeaking()
        speaking_test.setup_method()
        self.session_id = speaking_test.test_create_session()
    
    def test_get_report(self):
        """测试获取报告"""
        response = requests.get(f"{BASE_URL}/report/{self.session_id}", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "summary" in response.json()
        assert "scores" in response.json()
        assert "suggestions" in response.json()

class TestProfile:
    """测试用户档案模块"""
    
    def setup_method(self):
        """设置测试环境"""
        auth_test = TestAuth()
        self.token = auth_test.test_login_phone()
    
    def test_get_profile(self):
        """测试获取用户档案"""
        response = requests.get(f"{BASE_URL}/profile/me", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "user_id" in response.json()
        assert "target_band" in response.json()
    
    def test_update_profile(self):
        """测试更新用户档案"""
        response = requests.put(f"{BASE_URL}/profile/me", json={
            "target_band": 7.5,
            "current_band_overall": 6.0
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "user_id" in response.json()
        assert response.json()["target_band"] == 7.5

class TestPlan:
    """测试学习计划模块"""
    
    def setup_method(self):
        """设置测试环境"""
        auth_test = TestAuth()
        self.token = auth_test.test_login_phone()
    
    def test_generate_7d_plan(self):
        """测试生成7天计划"""
        response = requests.post(f"{BASE_URL}/plan/7d", json={
            "weaknesses": ["lack of linking words", "limited vocabulary"],
            "target_score": 7.0
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "plan" in response.json()
        assert "summary" in response.json()
        assert len(response.json()["plan"]) == 7
    
    def test_create_plan(self):
        """测试创建学习计划"""
        response = requests.post(f"{BASE_URL}/plan/create", json={
            "target_band": 7.0,
            "daily_minutes": 60,
            "focus_modules": ["speaking", "writing"],
            "duration_weeks": 4
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "plan_id" in response.json()
        assert "plan" in response.json()
        return response.json()["plan_id"]
    
    def test_get_plan_detail(self):
        """测试获取计划详情"""
        plan_id = self.test_create_plan()
        response = requests.get(f"{BASE_URL}/plan/{plan_id}", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "plan_id" in response.json()
        assert response.json()["plan_id"] == plan_id
    
    def test_get_plan_list(self):
        """测试获取用户计划列表"""
        response = requests.get(f"{BASE_URL}/plan", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_update_plan_status(self):
        """测试更新计划状态"""
        plan_id = self.test_create_plan()
        response = requests.put(f"{BASE_URL}/plan/{plan_id}/status", json={
            "status": "active"
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "status" in response.json()
    
    def test_create_daily_tasks(self):
        """测试创建每日任务"""
        plan_id = self.test_create_plan()
        response = requests.post(f"{BASE_URL}/plan/{plan_id}/tasks", json={
            "date": "2024-01-01",
            "tasks": [
                {
                    "title": "Speaking Practice",
                    "duration_minutes": 30
                }
            ]
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_get_plan_tasks(self):
        """测试获取计划任务列表"""
        plan_id = self.test_create_plan()
        response = requests.get(f"{BASE_URL}/plan/{plan_id}/tasks", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_get_specific_date_tasks(self):
        """测试获取指定日期任务"""
        plan_id = self.test_create_plan()
        date = "2024-01-01"
        response = requests.get(f"{BASE_URL}/plan/{plan_id}/tasks/{date}", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
    
    def test_update_task_complete(self):
        """测试更新任务完成状态"""
        plan_id = self.test_create_plan()
        # 先创建任务
        create_response = requests.post(f"{BASE_URL}/plan/{plan_id}/tasks", json={
            "date": "2024-01-01",
            "tasks": [
                {
                    "title": "Speaking Practice",
                    "duration_minutes": 30
                }
            ]
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        task_id = create_response.json()[0]["task_id"]
        
        # 更新完成状态
        response = requests.put(f"{BASE_URL}/plan/tasks/{task_id}/complete", json={
            "completed": True
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "completed" in response.json()
    
    def test_update_task_progress(self):
        """测试更新任务进度"""
        plan_id = self.test_create_plan()
        # 先创建任务
        create_response = requests.post(f"{BASE_URL}/plan/{plan_id}/tasks", json={
            "date": "2024-01-01",
            "tasks": [
                {
                    "title": "Speaking Practice",
                    "duration_minutes": 30
                }
            ]
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        task_id = create_response.json()[0]["task_id"]
        
        # 更新进度
        response = requests.put(f"{BASE_URL}/plan/tasks/{task_id}/progress", json={
            "progress": 50
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "progress" in response.json()
    
    def test_get_plan_progress(self):
        """测试获取计划进度"""
        plan_id = self.test_create_plan()
        response = requests.get(f"{BASE_URL}/plan/{plan_id}/progress", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "overall_progress" in response.json()

class TestReading:
    """测试阅读模块"""
    
    def setup_method(self):
        """设置测试环境"""
        auth_test = TestAuth()
        self.token = auth_test.test_login_phone()
    
    def test_recognize_synonyms(self):
        """测试识别同义词"""
        response = requests.post(f"{BASE_URL}/reading/synonyms", json={
            "text": "It is important to improve your English skills to solve problems and find solutions.",
            "topic": "education"
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "results" in response.json()
        assert isinstance(response.json()["results"], list)
    
    def test_analyze_passage(self):
        """测试分析文章"""
        response = requests.post(f"{BASE_URL}/reading/analyze", json={
            "text": "This is a test passage. It contains multiple sentences. Some of them are long and complex."
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "difficulty" in response.json()
        assert "synonym_count" in response.json()
    
    def test_analyze_long_sentences(self):
        """测试分析长难句"""
        response = requests.post(f"{BASE_URL}/reading/long-sentences", json={
            "text": "Although it is generally accepted that the Earth is round, there are still some people who believe it is flat, despite overwhelming scientific evidence to the contrary."
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "sentences" in response.json()
        assert isinstance(response.json()["sentences"], list)
    
    def test_get_common_synonyms(self):
        """测试获取常见同义词"""
        response = requests.get(f"{BASE_URL}/reading/common-synonyms", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert isinstance(response.json(), list)

class TestWriting:
    """测试写作模块"""
    
    def setup_method(self):
        """设置测试环境"""
        auth_test = TestAuth()
        self.token = auth_test.test_login_phone()
    
    def test_analyze_task1(self):
        """测试分析Task 1写作"""
        response = requests.post(f"{BASE_URL}/writing/task1/analyze", json={
            "text": "The line graph illustrates changes in the number of people using smartphones in the UK from 2010 to 2020.",
            "chart_type": "graph",
            "topic": "Smartphone Usage",
            "keywords": ["smartphone", "usage", "trend"]
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "structure_score" in response.json()
        assert "content_score" in response.json()
        assert "vocabulary_score" in response.json()
        assert "grammar_score" in response.json()
    
    def test_save_task1_practice(self):
        """测试保存Task 1练习"""
        response = requests.post(f"{BASE_URL}/writing/task1/practice", json={
            "text": "The line graph illustrates changes in the number of people using smartphones in the UK from 2010 to 2020.",
            "chart_type": "graph",
            "topic": "Smartphone Usage",
            "keywords": ["smartphone", "usage", "trend"]
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "practice_id" in response.json()
    
    def test_get_task1_practices(self):
        """测试获取Task 1练习历史"""
        response = requests.get(f"{BASE_URL}/writing/task1/practices", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_get_task1_common_structures(self):
        """测试获取Task 1常用结构"""
        response = requests.get(f"{BASE_URL}/writing/task1/common-structures", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_get_task1_common_vocabulary(self):
        """测试获取Task 1常用词汇"""
        response = requests.get(f"{BASE_URL}/writing/task1/common-vocabulary", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert isinstance(response.json(), list)

class TestListening:
    """测试听力模块"""
    
    def setup_method(self):
        """设置测试环境"""
        auth_test = TestAuth()
        self.token = auth_test.test_login_phone()
    
    def test_get_library(self):
        """测试获取音频库"""
        response = requests.get(f"{BASE_URL}/listening/library", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert isinstance(response.json(), list)
        return response.json()[0]["id"] if response.json() else "audio_001"
    
    def test_get_audio_file(self):
        """测试获取音频文件信息"""
        audio_id = self.test_get_library()
        response = requests.get(f"{BASE_URL}/listening/file/{audio_id}", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "id" in response.json()
    
    def test_start_playback(self):
        """测试开始播放"""
        response = requests.post(f"{BASE_URL}/listening/start", json={
            "audio_id": "audio_001"
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "status" in response.json()
    
    def test_pause_playback(self):
        """测试暂停播放"""
        # 先开始播放
        requests.post(f"{BASE_URL}/listening/start", json={
            "audio_id": "audio_001"
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        
        # 测试暂停
        response = requests.post(f"{BASE_URL}/listening/pause", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "status" in response.json()
    
    def test_resume_playback(self):
        """测试继续播放"""
        # 先开始播放并暂停
        requests.post(f"{BASE_URL}/listening/start", json={
            "audio_id": "audio_001"
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        requests.post(f"{BASE_URL}/listening/pause", headers={
            "Authorization": f"Bearer {self.token}"
        })
        
        # 测试继续播放
        response = requests.post(f"{BASE_URL}/listening/resume", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "status" in response.json()
    
    def test_stop_playback(self):
        """测试停止播放"""
        # 先开始播放
        requests.post(f"{BASE_URL}/listening/start", json={
            "audio_id": "audio_001"
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        
        # 测试停止
        response = requests.post(f"{BASE_URL}/listening/stop", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "status" in response.json()
    
    def test_set_speed(self):
        """测试设置语速"""
        response = requests.post(f"{BASE_URL}/listening/set-speed", json={
            "speed": 1.0
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "speed" in response.json()
    
    def test_set_position(self):
        """测试设置播放位置"""
        response = requests.post(f"{BASE_URL}/listening/set-position", json={
            "position": 10
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "position" in response.json()
    
    def test_get_playback_status(self):
        """测试获取播放状态"""
        response = requests.get(f"{BASE_URL}/listening/status", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "status" in response.json()
    
    def test_get_audio_segment(self):
        """测试获取音频片段"""
        audio_id = self.test_get_library()
        response = requests.get(f"{BASE_URL}/listening/segment/{audio_id}", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "segment" in response.json()

class TestHistory:
    """测试历史记录模块"""
    
    def setup_method(self):
        """设置测试环境"""
        auth_test = TestAuth()
        self.token = auth_test.test_login_phone()
    
    def test_get_sessions(self):
        """测试获取最近会话"""
        response = requests.get(f"{BASE_URL}/history/sessions", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert isinstance(response.json(), list)

class TestChat:
    """测试智能体对话模块"""
    
    def setup_method(self):
        """设置测试环境"""
        auth_test = TestAuth()
        self.token = auth_test.test_login_phone()
    
    def test_chat(self):
        """测试与智能体对话"""
        response = requests.post(f"{BASE_URL}/chat", json={
            "query": "How to improve my speaking fluency?",
            "session_id": "test_session"
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "agent" in response.json()
        assert "response" in response.json()
    
    def test_translation(self):
        """测试翻译练习"""
        response = requests.post(f"{BASE_URL}/chat/translation", json={
            "text": "Hello, how are you?",
            "target_language": "Chinese"
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "translation" in response.json()

class TestDiagnostic:
    """测试诊断测试模块"""
    
    def setup_method(self):
        """设置测试环境"""
        auth_test = TestAuth()
        self.token = auth_test.test_login_phone()
    
    def test_start_diagnostic(self):
        """测试开始诊断测试"""
        response = requests.post(f"{BASE_URL}/diagnostic/start", json={
            "modules": ["listening", "reading"]
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "id" in response.json()
        assert "modules" in response.json()
        return response.json()["id"]
    
    def test_submit_answer(self):
        """测试提交答案"""
        session_id = self.test_start_diagnostic()
        response = requests.post(f"{BASE_URL}/diagnostic/{session_id}/answer", json={
            "question_id": "q1",
            "answer": "A"
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "success" in response.json()
    
    def test_get_diagnostic_report(self):
        """测试获取诊断报告"""
        session_id = self.test_start_diagnostic()
        response = requests.get(f"{BASE_URL}/diagnostic/{session_id}/report", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "summary" in response.json()
    
    def test_complete_diagnostic(self):
        """测试完成诊断测试"""
        session_id = self.test_start_diagnostic()
        response = requests.post(f"{BASE_URL}/diagnostic/{session_id}/complete", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "success" in response.json()

class TestReminder:
    """测试提醒模块"""
    
    def setup_method(self):
        """设置测试环境"""
        auth_test = TestAuth()
        self.token = auth_test.test_login_phone()
    
    def test_create_reminder(self):
        """测试创建提醒"""
        scheduled_at = int(time.time()) + 3600  # 1小时后
        response = requests.post(f"{BASE_URL}/reminder", json={
            "title": "Test Reminder",
            "content": "This is a test reminder",
            "scheduled_at": scheduled_at
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "id" in response.json()
        assert "title" in response.json()
        return response.json()["id"]
    
    def test_get_reminders(self):
        """测试获取提醒列表"""
        response = requests.get(f"{BASE_URL}/reminder", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_get_reminder_detail(self):
        """测试获取提醒详情"""
        reminder_id = self.test_create_reminder()
        response = requests.get(f"{BASE_URL}/reminder/{reminder_id}", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "id" in response.json()
        assert response.json()["id"] == reminder_id
    
    def test_update_reminder_status(self):
        """测试更新提醒状态"""
        reminder_id = self.test_create_reminder()
        response = requests.put(f"{BASE_URL}/reminder/{reminder_id}/status", json={
            "status": "completed"
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "status" in response.json()
    
    def test_delete_reminder(self):
        """测试删除提醒"""
        reminder_id = self.test_create_reminder()
        response = requests.delete(f"{BASE_URL}/reminder/{reminder_id}", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "success" in response.json()
    
    def test_get_reminder_preferences(self):
        """测试获取提醒偏好设置"""
        response = requests.get(f"{BASE_URL}/reminder/preferences/me", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "user_id" in response.json()
    
    def test_update_reminder_preferences(self):
        """测试更新提醒偏好设置"""
        response = requests.put(f"{BASE_URL}/reminder/preferences/me", json={
            "timezone": "Asia/Shanghai",
            "reminder_time": "09:00"
        }, headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "user_id" in response.json()

class TestStats:
    """测试统计模块"""
    
    def setup_method(self):
        """设置测试环境"""
        auth_test = TestAuth()
        self.token = auth_test.test_login_phone()
    
    def test_get_overview(self):
        """测试获取统计概览"""
        response = requests.get(f"{BASE_URL}/stats/overview", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "total_events" in response.json()
        assert "event_counts" in response.json()
    
    def test_get_activities(self):
        """测试获取活动列表"""
        response = requests.get(f"{BASE_URL}/stats/activities", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_get_events(self):
        """测试获取事件列表"""
        response = requests.get(f"{BASE_URL}/stats/events", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert isinstance(response.json(), list)
    
    def test_get_detailed_stats(self):
        """测试获取详细统计"""
        response = requests.get(f"{BASE_URL}/stats/detailed", headers={
            "Authorization": f"Bearer {self.token}"
        })
        assert response.status_code == 200
        assert "modules" in response.json()

if __name__ == "__main__":
    # 运行所有测试
    pytest.main([__file__, "-v"])
