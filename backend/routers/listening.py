from fastapi import APIRouter, Depends
from pydantic import BaseModel
from typing import List, Optional
from ..deps import get_current_user

router = APIRouter()

# 音频文件信息模型
class AudioFile(BaseModel):
    id: str
    title: str
    duration: float  # in seconds
    url: str
    transcript: Optional[str] = None
    difficulty: str = "intermediate"

# 播放状态模型
class PlaybackStatus(BaseModel):
    audio_id: Optional[str] = None
    is_playing: bool = False
    current_time: float = 0.0  # in seconds
    speed: float = 1.0  # 0.5x - 2.0x
    volume: float = 1.0  # 0.0 - 1.0
    total_duration: float = 0.0  # in seconds

# 播放器控制请求模型
class PlaybackControlRequest(BaseModel):
    audio_id: Optional[str] = None
    current_time: Optional[float] = None

class SpeedControlRequest(BaseModel):
    speed: float  # 0.5x - 2.0x

# 模拟音频库
mock_audio_library = {
    "audio_001": {
        "id": "audio_001",
        "title": "IELTS Listening Practice Test 1 - Section 1",
        "duration": 600.0,  # 10 minutes
        "url": "http://example.com/audio001.mp3",
        "transcript": "This is a sample transcript...",
        "difficulty": "easy"
    },
    "audio_002": {
        "id": "audio_002",
        "title": "IELTS Listening Practice Test 1 - Section 2",
        "duration": 720.0,  # 12 minutes
        "url": "http://example.com/audio002.mp3",
        "transcript": "Another sample transcript...",
        "difficulty": "intermediate"
    },
    "audio_003": {
        "id": "audio_003",
        "title": "IELTS Listening Practice Test 2 - Section 3",
        "duration": 840.0,  # 14 minutes
        "url": "http://example.com/audio003.mp3",
        "transcript": "Advanced sample transcript...",
        "difficulty": "advanced"
    }
}

# 模拟播放状态存储（实际项目中应使用数据库或Redis）
player_states = {}

@router.get("/library", response_model=List[AudioFile])
async def get_audio_library(current_user: dict = Depends(get_current_user)):
    """获取音频库列表"""
    return [AudioFile(**audio) for audio in mock_audio_library.values()]

@router.get("/file/{audio_id}", response_model=AudioFile)
async def get_audio_file(audio_id: str, current_user: dict = Depends(get_current_user)):
    """获取单个音频文件信息"""
    if audio_id not in mock_audio_library:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Audio file not found")
    return AudioFile(**mock_audio_library[audio_id])

@router.post("/start", response_model=PlaybackStatus)
async def start_playback(req: PlaybackControlRequest, current_user: dict = Depends(get_current_user)):
    """开始播放音频"""
    user_id = current_user["id"]
    if not req.audio_id:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Audio ID required")
    
    if req.audio_id not in mock_audio_library:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    audio_info = mock_audio_library[req.audio_id]
    player_states[user_id] = {
        "audio_id": req.audio_id,
        "is_playing": True,
        "current_time": req.current_time or 0.0,
        "speed": 1.0,
        "volume": 1.0,
        "total_duration": audio_info["duration"]
    }
    return PlaybackStatus(**player_states[user_id])

@router.post("/pause", response_model=PlaybackStatus)
async def pause_playback(req: PlaybackControlRequest, current_user: dict = Depends(get_current_user)):
    """暂停播放"""
    user_id = current_user["id"]
    if user_id not in player_states:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="No active playback")
    
    player_states[user_id]["is_playing"] = False
    if req.current_time is not None:
        player_states[user_id]["current_time"] = req.current_time
    
    return PlaybackStatus(**player_states[user_id])

@router.post("/resume", response_model=PlaybackStatus)
async def resume_playback(req: PlaybackControlRequest, current_user: dict = Depends(get_current_user)):
    """继续播放"""
    user_id = current_user["id"]
    if user_id not in player_states:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="No playback to resume")
    
    player_states[user_id]["is_playing"] = True
    if req.current_time is not None:
        player_states[user_id]["current_time"] = req.current_time
    
    return PlaybackStatus(**player_states[user_id])

@router.post("/stop", response_model=PlaybackStatus)
async def stop_playback(current_user: dict = Depends(get_current_user)):
    """停止播放"""
    user_id = current_user["id"]
    if user_id not in player_states:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="No active playback")
    
    # Reset playback state
    player_states[user_id] = {
        "audio_id": None,
        "is_playing": False,
        "current_time": 0.0,
        "speed": 1.0,
        "volume": 1.0,
        "total_duration": 0.0
    }
    return PlaybackStatus(**player_states[user_id])

@router.post("/set-speed", response_model=PlaybackStatus)
async def set_speed(req: SpeedControlRequest, current_user: dict = Depends(get_current_user)):
    """设置播放语速（0.5x - 2.0x）"""
    user_id = current_user["id"]
    if user_id not in player_states:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="No active playback")
    
    # Validate speed range
    if not (0.5 <= req.speed <= 2.0):
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Speed must be between 0.5x and 2.0x")
    
    player_states[user_id]["speed"] = req.speed
    return PlaybackStatus(**player_states[user_id])

@router.post("/set-position", response_model=PlaybackStatus)
async def set_position(req: PlaybackControlRequest, current_user: dict = Depends(get_current_user)):
    """设置播放位置"""
    user_id = current_user["id"]
    if user_id not in player_states:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="No active playback")
    
    if req.current_time is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=400, detail="Current time required")
    
    player_states[user_id]["current_time"] = req.current_time
    return PlaybackStatus(**player_states[user_id])

@router.get("/status", response_model=PlaybackStatus)
async def get_playback_status(current_user: dict = Depends(get_current_user)):
    """获取当前播放状态"""
    user_id = current_user["id"]
    if user_id not in player_states:
        # Return default status if no active playback
        return PlaybackStatus()
    return PlaybackStatus(**player_states[user_id])

# 辅助功能：获取音频片段
@router.get("/segment/{audio_id}")
async def get_audio_segment(audio_id: str, start_time: float = 0.0, end_time: float = 30.0, current_user: dict = Depends(get_current_user)):
    """获取音频片段信息（用于精听练习）"""
    if audio_id not in mock_audio_library:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="Audio file not found")
    
    audio_info = mock_audio_library[audio_id]
    # 实际项目中应返回真实的音频片段URL，这里仅返回信息
    return {
        "audio_id": audio_id,
        "start_time": start_time,
        "end_time": end_time,
        "duration": min(end_time - start_time, audio_info["duration"] - start_time),
        "url": f"{audio_info['url']}?start={start_time}&end={end_time}",
        "transcript": audio_info["transcript"][:100] if audio_info["transcript"] else None
    }