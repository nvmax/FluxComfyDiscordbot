from typing import Callable, NoReturn
from tqdm.auto import tqdm

def format_time(seconds):
    """Format time in seconds to a human-readable string."""
    if seconds < 60:
        return f"{seconds:.0f}s"
    elif seconds < 3600:
        minutes = seconds / 60
        return f"{minutes:.0f}m"
    else:
        hours = seconds / 3600
        return f"{hours:.1f}h"

def patch_tqdm(progress_callback: Callable[..., NoReturn]):
    """Monkey patches tqdm to update the progress in the UI when downloading models."""
    original_update = tqdm.update

    def patched_update(self, n=1):
        if self.n is not None and self.total is not None:
            downloaded = self.n / 1024 / 1024
            total_size = self.total / 1024 / 1024
            speed = (
                self.format_dict["rate"] / 1024 / 1024
                if self.format_dict["rate"]
                else 0.001
            )
            time_left = format_time((total_size - downloaded) / speed)
            progress_msg = f"Downloaded: {int(downloaded)}/{int(total_size)} MB Speed: {speed:.2f} MB/s Remaining: {time_left}"
            if progress_callback:
                progress_callback(self.n / self.total, progress_msg)

        return original_update(self, n)

    tqdm.update = patched_update
