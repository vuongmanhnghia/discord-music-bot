from enum import Enum

class SongStatus(Enum):
    """Song processing status"""

    PENDING = "pending"
    PROCESSING = "processing"
    READY = "ready"
    FAILED = "failed"