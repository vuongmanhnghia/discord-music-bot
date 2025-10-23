from abc import ABC, abstractmethod
from ..entities.song import Song


# Abstract interfaces for processors
class SongProcessor(ABC):
    """Abstract base for song processors"""

    @abstractmethod
    async def can_process(self, song: Song) -> bool:
        """Check if this processor can handle the song"""
        pass

    @abstractmethod
    async def process(self, song: Song) -> bool:
        """Process the song and update its state"""
        pass
