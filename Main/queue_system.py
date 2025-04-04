import asyncio
import json
import logging
import time
import os
import sqlite3
from typing import Dict, List, Optional, Any, Tuple, Union
from dataclasses import asdict
import uuid

from Main.custom_commands.models import RequestItem, ReduxRequestItem, ReduxPromptRequestItem, BaseRequestItem

logger = logging.getLogger(__name__)

class QueuePriority:
    """Priority levels for queue items"""
    HIGH = 0
    NORMAL = 1
    LOW = 2

class QueueStatus:
    """Status values for queue items"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"

class QueueItem:
    """Represents an item in the queue with metadata"""
    
    def __init__(self, 
                 request_id: str,
                 request_item: Union[RequestItem, ReduxRequestItem, ReduxPromptRequestItem],
                 priority: int = QueuePriority.NORMAL,
                 user_id: str = None,
                 added_at: float = None):
        self.request_id = request_id
        self.request_item = request_item
        self.priority = priority
        self.user_id = user_id or request_item.user_id
        self.added_at = added_at or time.time()
        self.started_at: Optional[float] = None
        self.completed_at: Optional[float] = None
        self.status = QueueStatus.PENDING
        self.error_message: Optional[str] = None
        
    def to_dict(self) -> Dict[str, Any]:
        """Convert queue item to dictionary for serialization"""
        result = {
            "request_id": self.request_id,
            "request_type": self.request_item.__class__.__name__,
            "request_data": asdict(self.request_item),
            "priority": self.priority,
            "user_id": self.user_id,
            "added_at": self.added_at,
            "started_at": self.started_at,
            "completed_at": self.completed_at,
            "status": self.status,
            "error_message": self.error_message
        }
        return result
        
    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'QueueItem':
        """Create queue item from dictionary"""
        request_type = data["request_type"]
        request_data = data["request_data"]
        
        # Create the appropriate request item based on type
        if request_type == "RequestItem":
            request_item = RequestItem(**request_data)
        elif request_type == "ReduxRequestItem":
            request_item = ReduxRequestItem(**request_data)
        elif request_type == "ReduxPromptRequestItem":
            request_item = ReduxPromptRequestItem(**request_data)
        else:
            raise ValueError(f"Unknown request type: {request_type}")
            
        # Create queue item
        queue_item = cls(
            request_id=data["request_id"],
            request_item=request_item,
            priority=data["priority"],
            user_id=data["user_id"],
            added_at=data["added_at"]
        )
        
        # Set additional fields
        queue_item.started_at = data.get("started_at")
        queue_item.completed_at = data.get("completed_at")
        queue_item.status = data.get("status", QueueStatus.PENDING)
        queue_item.error_message = data.get("error_message")
        
        return queue_item

class QueueDatabase:
    """Database for persisting queue items"""
    
    def __init__(self, db_path: str = "queue_data.db"):
        self.db_path = db_path
        self._init_db()
        
    def _init_db(self):
        """Initialize the database schema"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Create queue items table
        c.execute('''
            CREATE TABLE IF NOT EXISTS queue_items (
                request_id TEXT PRIMARY KEY,
                request_data TEXT NOT NULL,
                priority INTEGER NOT NULL,
                user_id TEXT NOT NULL,
                added_at REAL NOT NULL,
                started_at REAL,
                completed_at REAL,
                status TEXT NOT NULL,
                error_message TEXT
            )
        ''')
        
        # Create user rate limits table
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_rate_limits (
                user_id TEXT PRIMARY KEY,
                request_count INTEGER NOT NULL,
                last_request_time REAL NOT NULL
            )
        ''')
        
        # Create queue stats table
        c.execute('''
            CREATE TABLE IF NOT EXISTS queue_stats (
                date TEXT PRIMARY KEY,
                total_requests INTEGER NOT NULL,
                completed_requests INTEGER NOT NULL,
                failed_requests INTEGER NOT NULL,
                avg_processing_time REAL NOT NULL
            )
        ''')
        
        conn.commit()
        conn.close()
        
    def save_queue_item(self, item: QueueItem):
        """Save a queue item to the database"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute(
            "INSERT OR REPLACE INTO queue_items VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (
                item.request_id,
                json.dumps(item.to_dict()),
                item.priority,
                item.user_id,
                item.added_at,
                item.started_at,
                item.completed_at,
                item.status,
                item.error_message
            )
        )
        
        conn.commit()
        conn.close()
        
    def load_pending_queue_items(self) -> List[QueueItem]:
        """Load all pending queue items from the database"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute(
            "SELECT request_data FROM queue_items WHERE status = ? ORDER BY priority, added_at",
            (QueueStatus.PENDING,)
        )
        
        items = []
        for row in c.fetchall():
            try:
                data = json.loads(row[0])
                item = QueueItem.from_dict(data)
                items.append(item)
            except Exception as e:
                logger.error(f"Error loading queue item: {e}")
                
        conn.close()
        return items
        
    def update_queue_item_status(self, request_id: str, status: str, 
                                error_message: Optional[str] = None,
                                started_at: Optional[float] = None,
                                completed_at: Optional[float] = None):
        """Update the status of a queue item"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # First get the current item data
        c.execute("SELECT request_data FROM queue_items WHERE request_id = ?", (request_id,))
        row = c.fetchone()
        
        if row:
            try:
                data = json.loads(row[0])
                item = QueueItem.from_dict(data)
                
                # Update the item
                item.status = status
                if error_message is not None:
                    item.error_message = error_message
                if started_at is not None:
                    item.started_at = started_at
                if completed_at is not None:
                    item.completed_at = completed_at
                    
                # Save the updated item
                self.save_queue_item(item)
                
                # Update stats if completed or failed
                if status in [QueueStatus.COMPLETED, QueueStatus.FAILED]:
                    self._update_stats(item)
                    
            except Exception as e:
                logger.error(f"Error updating queue item status: {e}")
        
        conn.close()
        
    def _update_stats(self, item: QueueItem):
        """Update queue statistics"""
        if not (item.started_at and item.completed_at):
            return
            
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Get today's date as string
        today = time.strftime("%Y-%m-%d")
        
        # Check if we have stats for today
        c.execute("SELECT * FROM queue_stats WHERE date = ?", (today,))
        row = c.fetchone()
        
        processing_time = item.completed_at - item.started_at
        
        if row:
            # Update existing stats
            date, total, completed, failed, avg_time = row
            
            new_total = total + 1
            new_completed = completed + (1 if item.status == QueueStatus.COMPLETED else 0)
            new_failed = failed + (1 if item.status == QueueStatus.FAILED else 0)
            
            # Calculate new average processing time
            new_avg_time = ((avg_time * total) + processing_time) / new_total
            
            c.execute(
                "UPDATE queue_stats SET total_requests = ?, completed_requests = ?, failed_requests = ?, avg_processing_time = ? WHERE date = ?",
                (new_total, new_completed, new_failed, new_avg_time, today)
            )
        else:
            # Create new stats entry
            completed = 1 if item.status == QueueStatus.COMPLETED else 0
            failed = 1 if item.status == QueueStatus.FAILED else 0
            
            c.execute(
                "INSERT INTO queue_stats VALUES (?, ?, ?, ?, ?)",
                (today, 1, completed, failed, processing_time)
            )
            
        conn.commit()
        conn.close()
        
    def get_user_request_count(self, user_id: str, time_window: float = 3600) -> int:
        """Get the number of requests a user has made in the given time window"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        # Get current time
        current_time = time.time()
        cutoff_time = current_time - time_window
        
        c.execute(
            "SELECT COUNT(*) FROM queue_items WHERE user_id = ? AND added_at > ?",
            (user_id, cutoff_time)
        )
        
        count = c.fetchone()[0]
        conn.close()
        
        return count
        
    def update_user_rate_limit(self, user_id: str):
        """Update the rate limit information for a user"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        current_time = time.time()
        
        # Check if user exists
        c.execute("SELECT request_count FROM user_rate_limits WHERE user_id = ?", (user_id,))
        row = c.fetchone()
        
        if row:
            # Update existing record
            count = row[0] + 1
            c.execute(
                "UPDATE user_rate_limits SET request_count = ?, last_request_time = ? WHERE user_id = ?",
                (count, current_time, user_id)
            )
        else:
            # Create new record
            c.execute(
                "INSERT INTO user_rate_limits VALUES (?, ?, ?)",
                (user_id, 1, current_time)
            )
            
        conn.commit()
        conn.close()
        
    def get_queue_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get queue statistics for the last N days"""
        conn = sqlite3.connect(self.db_path)
        c = conn.cursor()
        
        c.execute(
            "SELECT * FROM queue_stats ORDER BY date DESC LIMIT ?",
            (days,)
        )
        
        stats = []
        for row in c.fetchall():
            date, total, completed, failed, avg_time = row
            stats.append({
                "date": date,
                "total_requests": total,
                "completed_requests": completed,
                "failed_requests": failed,
                "avg_processing_time": avg_time
            })
            
        conn.close()
        return stats

class ImageGenerationQueue:
    """Enhanced queue system for image generation requests"""
    
    def __init__(self, max_concurrent: int = 3, rate_limit: int = 10, rate_window: float = 3600):
        """
        Initialize the queue system
        
        Args:
            max_concurrent: Maximum number of concurrent requests to process
            rate_limit: Maximum number of requests per user in the rate window
            rate_window: Time window for rate limiting in seconds (default: 1 hour)
        """
        self.queue = asyncio.PriorityQueue()
        self.processing = {}  # request_id -> QueueItem
        self.db = QueueDatabase()
        self.max_concurrent = max_concurrent
        self.rate_limit = rate_limit
        self.rate_window = rate_window
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self._load_pending_items()
        
    def _load_pending_items(self):
        """Load pending items from the database"""
        items = self.db.load_pending_queue_items()
        logger.info(f"Loaded {len(items)} pending queue items from database")
        
        # Add items to the queue
        for item in items:
            self._add_to_queue(item)
            
    def _add_to_queue(self, item: QueueItem):
        """Add an item to the priority queue"""
        # Priority queue sorts by first element of tuple
        self.queue.put_nowait((item.priority, item.added_at, item))
        
    async def add_request(self, 
                         request_item: Union[RequestItem, ReduxRequestItem, ReduxPromptRequestItem],
                         priority: int = QueuePriority.NORMAL) -> Tuple[bool, str, str]:
        """
        Add a request to the queue
        
        Args:
            request_item: The request item to add
            priority: Priority level for the request
            
        Returns:
            Tuple of (success, request_id, message)
        """
        user_id = request_item.user_id
        
        # Check rate limit
        request_count = self.db.get_user_request_count(user_id, self.rate_window)
        if request_count >= self.rate_limit:
            return False, "", f"Rate limit exceeded. You can make {self.rate_limit} requests per {self.rate_window/3600:.1f} hours."
            
        # Create queue item
        request_id = str(uuid.uuid4())
        item = QueueItem(
            request_id=request_id,
            request_item=request_item,
            priority=priority,
            user_id=user_id
        )
        
        # Save to database
        self.db.save_queue_item(item)
        self.db.update_user_rate_limit(user_id)
        
        # Add to queue
        self._add_to_queue(item)
        
        position = self.queue.qsize()
        return True, request_id, f"Request added to queue. Position: {position}"
        
    async def get_next_request(self) -> Optional[QueueItem]:
        """Get the next request from the queue"""
        if self.queue.empty():
            return None
            
        # Get item from queue
        _, _, item = await self.queue.get()
        
        # Update status
        item.status = QueueStatus.PROCESSING
        item.started_at = time.time()
        self.processing[item.request_id] = item
        self.db.update_queue_item_status(
            item.request_id, 
            QueueStatus.PROCESSING,
            started_at=item.started_at
        )
        
        return item
        
    async def complete_request(self, request_id: str, success: bool, error_message: Optional[str] = None):
        """Mark a request as completed"""
        if request_id not in self.processing:
            logger.warning(f"Request {request_id} not found in processing queue")
            return
            
        item = self.processing[request_id]
        item.completed_at = time.time()
        
        if success:
            item.status = QueueStatus.COMPLETED
        else:
            item.status = QueueStatus.FAILED
            item.error_message = error_message
            
        # Update database
        self.db.update_queue_item_status(
            request_id,
            item.status,
            error_message=error_message,
            completed_at=item.completed_at
        )
        
        # Remove from processing
        del self.processing[request_id]
        
        # Mark task as done
        self.queue.task_done()
        
    async def cancel_request(self, request_id: str, user_id: str) -> bool:
        """
        Cancel a request
        
        Args:
            request_id: ID of the request to cancel
            user_id: ID of the user making the cancellation request
            
        Returns:
            True if cancelled successfully, False otherwise
        """
        # Check if request is in processing
        if request_id in self.processing:
            item = self.processing[request_id]
            
            # Only allow the request owner or admin to cancel
            if item.user_id != user_id:
                return False
                
            item.status = QueueStatus.CANCELLED
            item.completed_at = time.time()
            
            # Update database
            self.db.update_queue_item_status(
                request_id,
                QueueStatus.CANCELLED,
                completed_at=item.completed_at
            )
            
            # Remove from processing
            del self.processing[request_id]
            
            # Mark task as done
            self.queue.task_done()
            
            return True
            
        # If not in processing, it might be in the queue
        # Unfortunately, we can't easily remove from asyncio.PriorityQueue
        # So we'll mark it as cancelled in the database and skip it when processing
        self.db.update_queue_item_status(
            request_id,
            QueueStatus.CANCELLED,
            completed_at=time.time()
        )
        
        return True
        
    def get_queue_status(self) -> Dict[str, Any]:
        """Get the current status of the queue"""
        return {
            "queue_size": self.queue.qsize(),
            "processing": len(self.processing),
            "max_concurrent": self.max_concurrent
        }
        
    def get_user_queue_items(self, user_id: str) -> List[Dict[str, Any]]:
        """Get all queue items for a specific user"""
        conn = sqlite3.connect(self.db.db_path)
        c = conn.cursor()
        
        c.execute(
            "SELECT request_data FROM queue_items WHERE user_id = ? ORDER BY added_at DESC",
            (user_id,)
        )
        
        items = []
        for row in c.fetchall():
            try:
                data = json.loads(row[0])
                items.append(data)
            except Exception as e:
                logger.error(f"Error loading queue item: {e}")
                
        conn.close()
        return items
        
    def get_queue_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """Get queue statistics"""
        return self.db.get_queue_stats(days)
        
    async def process_queue(self, process_func):
        """
        Process the queue continuously
        
        Args:
            process_func: Async function that takes a QueueItem and processes it
        """
        while True:
            try:
                async with self.semaphore:
                    item = await self.get_next_request()
                    
                    if not item:
                        # No items in queue, wait a bit
                        await asyncio.sleep(1)
                        continue
                        
                    if item.status == QueueStatus.CANCELLED:
                        # Skip cancelled items
                        self.queue.task_done()
                        continue
                        
                    # Process the item
                    try:
                        success = await process_func(item)
                        await self.complete_request(item.request_id, success)
                    except Exception as e:
                        logger.error(f"Error processing queue item: {e}")
                        await self.complete_request(item.request_id, False, str(e))
                        
            except Exception as e:
                logger.error(f"Error in queue processing loop: {e}")
                await asyncio.sleep(5)  # Wait a bit before retrying
