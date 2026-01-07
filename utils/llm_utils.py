import json
import re
from typing import Any, Dict, Optional


def extract_json(text: str) -> Optional[Dict[str, Any]]:
    if not text:
        return None
    
    text = re.sub(r"```json|```", "", text, flags=re.IGNORECASE).strip()

    # 尝试直接 parse
    try:
        return json.loads(text)
    except Exception:
        pass

    # 提取第一个 JSON 块
    match = re.search(r"\{[\s\S]*\}", text)
    if not match:
        return None

    try:
        return json.loads(match.group())
    except Exception:
        return None