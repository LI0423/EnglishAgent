import json
import uuid
from dataclasses import asdict
from datetime import datetime
from typing import Optional

from rag_core.agentic.schemas import IterationTrace


class TraceLogger:
    def __init__(self, log_file: Optional[str] = None):
        self._log_file = log_file

    def new_trace_id(self) -> str:
        return str(uuid.uuid4())

    def log_iteration(self, trace_id: str, trace: IterationTrace) -> None:
        if not self._log_file:
            return

        payload = {
            "ts": datetime.utcnow().isoformat() + "Z",
            "trace_id": trace_id,
            "event": "iteration",
            "data": asdict(trace),
        }
        with open(self._log_file, "a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")
