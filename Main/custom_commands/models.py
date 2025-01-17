from dataclasses import dataclass
from typing import List, Optional, Union
import logging
import os

logger = logging.getLogger(__name__)

@dataclass
class BaseRequestItem:
    """Base class for all request items with common fields"""
    id: str
    user_id: str
    channel_id: str
    interaction_id: str
    original_message_id: str
    resolution: str
    workflow_filename: str

    def __post_init__(self):
        # Convert all string fields to strings and handle None values
        for field in self.__dataclass_fields__:
            if field not in ['upscale_factor', 'loras', 'seed', 'strength1', 'strength2', 'image1', 'image2']:
                value = getattr(self, field)
                setattr(self, field, str(value) if value is not None else '')

@dataclass
class RequestItem(BaseRequestItem):
    """Original request item for standard image generation"""
    prompt: str
    loras: List[str]
    upscale_factor: int
    seed: Optional[int] = None
    is_pulid: bool = False

    def __post_init__(self):
        super().__post_init__()
        
        # Handle upscale factor
        if self.upscale_factor is None:
            self.upscale_factor = 1
        else:
            self.upscale_factor = int(self.upscale_factor)

        # Handle seed
        if self.seed is not None:
            self.seed = int(self.seed)

@dataclass
class ReduxPromptRequestItem(BaseRequestItem):
    """Request item for ReduxPrompt image generation with one reference image and prompt"""
    prompt: str
    strength: str  # String value: highest, high, medium, low, lowest
    image_path: str  # Path to the saved image file
    image_filename: str
    seed: Optional[int] = None  # Optional seed value for generation

    def __post_init__(self):
        super().__post_init__()
        
        # Validate strength value
        valid_strengths = ['highest', 'high', 'medium', 'low', 'lowest']
        if self.strength not in valid_strengths:
            raise ValueError(f"Strength must be one of: {', '.join(valid_strengths)}")

        # Validate image path exists
        if not os.path.exists(self.image_path):
            logger.error(f"Image file not found at path: {self.image_path}")
            raise ValueError(f"Image file not found at path: {self.image_path}")

        # Validate filenames
        if not isinstance(self.image_filename, str):
            raise ValueError("Image filename must be a string")
            
        if not isinstance(self.workflow_filename, str):
            raise ValueError("Workflow filename must be a string")

        # Validate seed if provided
        if self.seed is not None and not isinstance(self.seed, int):
            try:
                self.seed = int(self.seed)
            except (TypeError, ValueError):
                raise ValueError("Seed must be an integer")

@dataclass
class ReduxRequestItem(BaseRequestItem):
    """Request item for Redux image generation with two reference images"""
    strength1: float
    strength2: float
    image1: bytes
    image2: bytes
    image1_filename: str
    image2_filename: str

    def __post_init__(self):
        super().__post_init__()
        
        # Validate strength values
        if not isinstance(self.strength1, float) or not isinstance(self.strength2, float):
            try:
                self.strength1 = float(self.strength1)
                self.strength2 = float(self.strength2)
            except (TypeError, ValueError) as e:
                raise ValueError("Strength values must be numbers") from e

        if not (0.1 <= self.strength1 <= 1.0 and 0.1 <= self.strength2 <= 1.0):
            raise ValueError("Strength values must be between 0.1 and 1.0")

        # Validate image data
        if not isinstance(self.image1, bytes) or not isinstance(self.image2, bytes):
            raise ValueError("Image data must be in bytes format")

        # Validate filenames
        if not isinstance(self.image1_filename, str) or not isinstance(self.image2_filename, str):
            raise ValueError("Filenames must be strings")