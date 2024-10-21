from dataclasses import dataclass
from typing import List, Optional

@dataclass
class RequestItem:
    id: str
    user_id: str
    channel_id: str
    interaction_id: str
    original_message_id: str
    prompt: str
    resolution: str
    loras: List[str]
    upscale_factor: int
    workflow_filename: str
    seed: Optional[int] = None

    def __post_init__(self):
        for field in self.__dataclass_fields__:
            if field not in ['upscale_factor', 'loras', 'seed']:
                value = getattr(self, field)
                if value is None:
                    setattr(self, field, '')
                else:
                    setattr(self, field, str(value))
        
        if self.upscale_factor is None:
            self.upscale_factor = 1
        else:
            self.upscale_factor = int(self.upscale_factor)

        if self.seed is not None:
            self.seed = int(self.seed)