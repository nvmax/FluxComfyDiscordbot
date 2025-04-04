import sqlite3
import logging
import time
import json
import os
import datetime
from typing import Dict, List, Any, Optional, Tuple
import matplotlib.pyplot as plt
from io import BytesIO
import discord

logger = logging.getLogger(__name__)

# Constants
ANALYTICS_DB = 'analytics.db'
STATS_INTERVAL = 3600  # 1 hour in seconds

class AnalyticsManager:
    """Manager for tracking and analyzing bot usage"""

    def __init__(self):
        """Initialize the analytics manager"""
        self._init_db()
        self.start_time = time.time()
        self.command_counts = {}
        self.user_counts = {}
        self.last_stats_time = time.time()

        # Migrate database if needed
        self.migrate_db()

    def _init_db(self):
        """Initialize the database schema"""
        conn = sqlite3.connect(ANALYTICS_DB)
        c = conn.cursor()

        # Create tables if they don't exist

        # Command usage table
        c.execute('''
            CREATE TABLE IF NOT EXISTS command_usage (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                command_name TEXT NOT NULL,
                user_id TEXT NOT NULL,
                guild_id TEXT,
                channel_id TEXT,
                timestamp REAL NOT NULL,
                execution_time REAL,
                success INTEGER NOT NULL
            )
        ''')

        # User activity table
        c.execute('''
            CREATE TABLE IF NOT EXISTS user_activity (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                guild_id TEXT,
                action_type TEXT NOT NULL,
                timestamp REAL NOT NULL,
                details TEXT
            )
        ''')

        # Image generation stats
        c.execute('''
            CREATE TABLE IF NOT EXISTS image_stats (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id TEXT NOT NULL,
                prompt TEXT,
                resolution TEXT,
                loras TEXT,
                upscale_factor INTEGER,
                generation_time REAL,
                is_video INTEGER DEFAULT 0,
                generation_type TEXT DEFAULT 'standard',
                timestamp REAL NOT NULL
            )
        ''')

        # Daily stats summary
        c.execute('''
            CREATE TABLE IF NOT EXISTS daily_stats (
                date TEXT PRIMARY KEY,
                total_commands INTEGER NOT NULL,
                total_images INTEGER NOT NULL,
                unique_users INTEGER NOT NULL,
                avg_generation_time REAL,
                popular_commands TEXT,
                popular_resolutions TEXT
            )
        ''')

        conn.commit()
        conn.close()

    def migrate_db(self):
        """Migrate the database to the latest schema"""
        try:
            conn = sqlite3.connect(ANALYTICS_DB)
            c = conn.cursor()

            # Check if is_video column exists in image_stats table
            c.execute("PRAGMA table_info(image_stats)")
            columns = [column[1] for column in c.fetchall()]

            # Add is_video column if it doesn't exist
            if 'is_video' not in columns:
                logger.info("Adding is_video column to image_stats table")
                c.execute("ALTER TABLE image_stats ADD COLUMN is_video INTEGER DEFAULT 0")
                conn.commit()
                logger.info("Added is_video column to image_stats table")

            # Add generation_type column if it doesn't exist
            if 'generation_type' not in columns:
                logger.info("Adding generation_type column to image_stats table")
                c.execute("ALTER TABLE image_stats ADD COLUMN generation_type TEXT DEFAULT 'standard'")
                conn.commit()
                logger.info("Added generation_type column to image_stats table")

            logger.info("Database migration completed successfully")

            conn.close()

        except Exception as e:
            logger.error(f"Error migrating database: {e}")

    def track_command(self, command_name: str, user_id: str, guild_id: Optional[str] = None,
                     channel_id: Optional[str] = None, execution_time: Optional[float] = None,
                     success: bool = True):
        """
        Track a command execution

        Args:
            command_name: Name of the command
            user_id: ID of the user who executed the command
            guild_id: ID of the guild where the command was executed
            channel_id: ID of the channel where the command was executed
            execution_time: Time taken to execute the command in seconds
            success: Whether the command executed successfully
        """
        try:
            conn = sqlite3.connect(ANALYTICS_DB)
            c = conn.cursor()

            c.execute(
                "INSERT INTO command_usage (command_name, user_id, guild_id, channel_id, timestamp, execution_time, success) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (command_name, user_id, guild_id, channel_id, time.time(), execution_time, 1 if success else 0)
            )

            conn.commit()
            conn.close()

            # Update in-memory counters
            if command_name not in self.command_counts:
                self.command_counts[command_name] = 0
            self.command_counts[command_name] += 1

            if user_id not in self.user_counts:
                self.user_counts[user_id] = 0
            self.user_counts[user_id] += 1

            # Check if it's time to generate daily stats
            current_time = time.time()
            if current_time - self.last_stats_time >= STATS_INTERVAL:
                self.generate_daily_stats()
                self.last_stats_time = current_time

        except Exception as e:
            logger.error(f"Error tracking command: {e}")

    def track_image_generation(self, user_id: str, prompt: str, resolution: str,
                              loras: List[str], upscale_factor: int, generation_time: float, is_video: bool = False):
        """
        Track an image generation

        Args:
            user_id: ID of the user who generated the image
            prompt: The prompt used for generation
            resolution: The resolution of the generated image
            loras: List of LoRAs used
            upscale_factor: Upscale factor used
            generation_time: Time taken to generate the image in seconds
            is_video: Whether this is a video generation (default: False)
        """
        try:
            # Log the generation time for debugging
            logger.info(f"Tracking image generation with time: {generation_time:.2f} seconds")

            conn = sqlite3.connect(ANALYTICS_DB)
            c = conn.cursor()

            c.execute(
                "INSERT INTO image_stats (user_id, prompt, resolution, loras, upscale_factor, generation_time, is_video, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                (user_id, prompt, resolution, json.dumps(loras), upscale_factor, generation_time, 1 if is_video else 0, time.time())
            )

            # Verify the data was inserted correctly
            c.execute("SELECT generation_time FROM image_stats WHERE user_id = ? ORDER BY timestamp DESC LIMIT 1", (user_id,))
            result = c.fetchone()
            if result:
                logger.info(f"Verified generation time in database: {result[0]:.2f} seconds")

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error tracking image generation: {e}")

    def track_user_activity(self, user_id: str, action_type: str, guild_id: Optional[str] = None, details: Optional[str] = None):
        """
        Track user activity

        Args:
            user_id: ID of the user
            action_type: Type of action (e.g., 'login', 'logout', 'join_server')
            guild_id: ID of the guild where the action occurred
            details: Additional details about the action
        """
        try:
            conn = sqlite3.connect(ANALYTICS_DB)
            c = conn.cursor()

            c.execute(
                "INSERT INTO user_activity (user_id, guild_id, action_type, timestamp, details) VALUES (?, ?, ?, ?, ?)",
                (user_id, guild_id, action_type, time.time(), details)
            )

            conn.commit()
            conn.close()

        except Exception as e:
            logger.error(f"Error tracking user activity: {e}")

    def generate_daily_stats(self):
        """Generate and store daily statistics"""
        try:
            conn = sqlite3.connect(ANALYTICS_DB)
            c = conn.cursor()

            # Get today's date
            today = datetime.datetime.now().strftime("%Y-%m-%d")

            # Calculate start of day timestamp
            start_of_day = datetime.datetime.combine(
                datetime.datetime.now().date(),
                datetime.time.min
            ).timestamp()

            # Get command stats
            c.execute(
                "SELECT COUNT(*), COUNT(DISTINCT user_id) FROM command_usage WHERE timestamp >= ?",
                (start_of_day,)
            )
            total_commands, unique_command_users = c.fetchone()

            # Get image stats
            c.execute(
                "SELECT COUNT(*), AVG(generation_time) FROM image_stats WHERE timestamp >= ?",
                (start_of_day,)
            )
            total_images, avg_generation_time = c.fetchone()

            # Get unique users
            c.execute(
                "SELECT COUNT(DISTINCT user_id) FROM (SELECT user_id FROM command_usage WHERE timestamp >= ? UNION SELECT user_id FROM image_stats WHERE timestamp >= ?)",
                (start_of_day, start_of_day)
            )
            unique_users = c.fetchone()[0]

            # Get popular commands
            c.execute(
                "SELECT command_name, COUNT(*) as count FROM command_usage WHERE timestamp >= ? GROUP BY command_name ORDER BY count DESC LIMIT 5",
                (start_of_day,)
            )
            popular_commands = {row[0]: row[1] for row in c.fetchall()}

            # Get popular resolutions
            c.execute(
                "SELECT resolution, COUNT(*) as count FROM image_stats WHERE timestamp >= ? GROUP BY resolution ORDER BY count DESC LIMIT 5",
                (start_of_day,)
            )
            popular_resolutions = {row[0]: row[1] for row in c.fetchall()}

            # Insert or update daily stats
            c.execute(
                "INSERT OR REPLACE INTO daily_stats VALUES (?, ?, ?, ?, ?, ?, ?)",
                (
                    today,
                    total_commands or 0,
                    total_images or 0,
                    unique_users or 0,
                    avg_generation_time or 0,
                    json.dumps(popular_commands),
                    json.dumps(popular_resolutions)
                )
            )

            conn.commit()
            conn.close()

            logger.info(f"Generated daily stats for {today}")

        except Exception as e:
            logger.error(f"Error generating daily stats: {e}")

    def get_command_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get command usage statistics for the last N days

        Args:
            days: Number of days to get stats for

        Returns:
            List of daily command stats
        """
        try:
            conn = sqlite3.connect(ANALYTICS_DB)
            c = conn.cursor()

            # Calculate timestamp for N days ago
            days_ago = time.time() - (days * 86400)

            # Get daily command counts
            c.execute(
                """
                SELECT
                    strftime('%Y-%m-%d', datetime(timestamp, 'unixepoch')) as date,
                    COUNT(*) as count
                FROM command_usage
                WHERE timestamp >= ?
                GROUP BY date
                ORDER BY date
                """,
                (days_ago,)
            )

            results = []
            for row in c.fetchall():
                date, count = row

                # Get command breakdown for this day
                c.execute(
                    """
                    SELECT
                        command_name,
                        COUNT(*) as count
                    FROM command_usage
                    WHERE timestamp >= ? AND timestamp < ?
                    GROUP BY command_name
                    ORDER BY count DESC
                    LIMIT 5
                    """,
                    (
                        datetime.datetime.strptime(date, "%Y-%m-%d").timestamp(),
                        datetime.datetime.strptime(date, "%Y-%m-%d").timestamp() + 86400
                    )
                )

                command_breakdown = {cmd: cnt for cmd, cnt in c.fetchall()}

                results.append({
                    "date": date,
                    "total_commands": count,
                    "command_breakdown": command_breakdown
                })

            conn.close()
            return results

        except Exception as e:
            logger.error(f"Error getting command stats: {e}")
            return []

    def get_image_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get image generation statistics for the last N days

        Args:
            days: Number of days to get stats for

        Returns:
            List of daily image stats
        """
        try:
            conn = sqlite3.connect(ANALYTICS_DB)
            c = conn.cursor()

            # Calculate timestamp for N days ago
            days_ago = time.time() - (days * 86400)

            # Get daily image counts and average generation time
            c.execute(
                """
                SELECT
                    strftime('%Y-%m-%d', datetime(timestamp, 'unixepoch')) as date,
                    COUNT(*) as count,
                    AVG(generation_time) as avg_time
                FROM image_stats
                WHERE timestamp >= ?
                GROUP BY date
                ORDER BY date
                """,
                (days_ago,)
            )

            results = []
            for row in c.fetchall():
                date, count, avg_time = row

                # Get resolution breakdown for this day
                c.execute(
                    """
                    SELECT
                        resolution,
                        COUNT(*) as count
                    FROM image_stats
                    WHERE timestamp >= ? AND timestamp < ?
                    GROUP BY resolution
                    ORDER BY count DESC
                    LIMIT 5
                    """,
                    (
                        datetime.datetime.strptime(date, "%Y-%m-%d").timestamp(),
                        datetime.datetime.strptime(date, "%Y-%m-%d").timestamp() + 86400
                    )
                )

                resolution_breakdown = {res: cnt for res, cnt in c.fetchall()}

                # Get average generation time for images and videos
                try:
                    # Get average generation time for images only
                    c.execute(
                        """
                        SELECT AVG(generation_time)
                        FROM image_stats
                        WHERE timestamp >= ? AND timestamp < ? AND is_video = 0
                        """,
                        (
                            datetime.datetime.strptime(date, "%Y-%m-%d").timestamp(),
                            datetime.datetime.strptime(date, "%Y-%m-%d").timestamp() + 86400
                        )
                    )
                    avg_image_time = c.fetchone()[0] or 0

                    # Get average generation time for videos only
                    c.execute(
                        """
                        SELECT AVG(generation_time)
                        FROM image_stats
                        WHERE timestamp >= ? AND timestamp < ? AND is_video = 1
                        """,
                        (
                            datetime.datetime.strptime(date, "%Y-%m-%d").timestamp(),
                            datetime.datetime.strptime(date, "%Y-%m-%d").timestamp() + 86400
                        )
                    )
                    avg_video_time = c.fetchone()[0] or 0
                except sqlite3.OperationalError as e:
                    # If the is_video column doesn't exist, use default values
                    logger.warning(f"Error getting video/image stats for day {date}: {e}")
                    avg_image_time = avg_time
                    avg_video_time = 0.0

                # Get video vs image breakdown for this day
                try:
                    c.execute(
                        """
                        SELECT
                            is_video,
                            COUNT(*) as count
                        FROM image_stats
                        WHERE timestamp >= ? AND timestamp < ?
                        GROUP BY is_video
                        """,
                        (
                            datetime.datetime.strptime(date, "%Y-%m-%d").timestamp(),
                            datetime.datetime.strptime(date, "%Y-%m-%d").timestamp() + 86400
                        )
                    )

                    video_breakdown = {}
                    for is_video, count in c.fetchall():
                        if is_video == 1:
                            video_breakdown["video"] = count
                        else:
                            video_breakdown["image"] = count

                    # If no video counts were found, set defaults
                    if "video" not in video_breakdown:
                        video_breakdown["video"] = 0
                    if "image" not in video_breakdown:
                        video_breakdown["image"] = 0
                except sqlite3.OperationalError as e:
                    # If the is_video column doesn't exist, use default values
                    logger.warning(f"Error getting video/image breakdown for day {date}: {e}")
                    video_breakdown = {"video": 0, "image": count}

                # Get generation type breakdown for this day
                try:
                    c.execute(
                        """
                        SELECT
                            generation_type,
                            COUNT(*) as count
                        FROM image_stats
                        WHERE timestamp >= ? AND timestamp < ?
                        GROUP BY generation_type
                        ORDER BY count DESC
                        """,
                        (
                            datetime.datetime.strptime(date, "%Y-%m-%d").timestamp(),
                            datetime.datetime.strptime(date, "%Y-%m-%d").timestamp() + 86400
                        )
                    )
                    type_breakdown = {typ if typ else "standard": cnt for typ, cnt in c.fetchall()}
                except sqlite3.OperationalError as e:
                    # If the generation_type column doesn't exist, use default values
                    logger.warning(f"Error getting generation type breakdown for day {date}: {e}")
                    type_breakdown = {"standard": count}

                results.append({
                    "date": date,
                    "total_images": count,
                    "avg_generation_time": avg_time,
                    "avg_image_time": avg_image_time,
                    "avg_video_time": avg_video_time,
                    "resolution_breakdown": resolution_breakdown,
                    "video_breakdown": video_breakdown,
                    "type_breakdown": type_breakdown
                })

            conn.close()
            return results

        except Exception as e:
            logger.error(f"Error getting image stats: {e}")
            return []

    def get_user_stats(self, days: int = 7) -> List[Dict[str, Any]]:
        """
        Get user activity statistics for the last N days

        Args:
            days: Number of days to get stats for

        Returns:
            List of daily user stats
        """
        try:
            conn = sqlite3.connect(ANALYTICS_DB)
            c = conn.cursor()

            # Calculate timestamp for N days ago
            days_ago = time.time() - (days * 86400)

            # Get daily unique user counts
            c.execute(
                """
                SELECT
                    strftime('%Y-%m-%d', datetime(timestamp, 'unixepoch')) as date,
                    COUNT(DISTINCT user_id) as unique_users
                FROM (
                    SELECT user_id, timestamp FROM command_usage WHERE timestamp >= ?
                    UNION
                    SELECT user_id, timestamp FROM image_stats WHERE timestamp >= ?
                )
                GROUP BY date
                ORDER BY date
                """,
                (days_ago, days_ago)
            )

            results = []
            for row in c.fetchall():
                date, unique_users = row

                # Get top users for this day
                c.execute(
                    """
                    SELECT
                        user_id,
                        COUNT(*) as count
                    FROM (
                        SELECT user_id, timestamp FROM command_usage
                        WHERE timestamp >= ? AND timestamp < ?
                        UNION ALL
                        SELECT user_id, timestamp FROM image_stats
                        WHERE timestamp >= ? AND timestamp < ?
                    )
                    GROUP BY user_id
                    ORDER BY count DESC
                    LIMIT 5
                    """,
                    (
                        datetime.datetime.strptime(date, "%Y-%m-%d").timestamp(),
                        datetime.datetime.strptime(date, "%Y-%m-%d").timestamp() + 86400,
                        datetime.datetime.strptime(date, "%Y-%m-%d").timestamp(),
                        datetime.datetime.strptime(date, "%Y-%m-%d").timestamp() + 86400
                    )
                )

                top_users = {user: cnt for user, cnt in c.fetchall()}

                results.append({
                    "date": date,
                    "unique_users": unique_users,
                    "top_users": top_users
                })

            conn.close()
            return results

        except Exception as e:
            logger.error(f"Error getting user stats: {e}")
            return []

    def reset_stats(self) -> bool:
        """
        Reset all analytics statistics

        Returns:
            True if successful, False otherwise
        """
        try:
            conn = sqlite3.connect(ANALYTICS_DB)
            c = conn.cursor()

            # Clear all tables
            c.execute("DELETE FROM command_usage")
            c.execute("DELETE FROM image_stats")
            c.execute("DELETE FROM user_activity")
            c.execute("DELETE FROM daily_stats")

            # Reset in-memory counters
            self.command_counts = {}
            self.user_counts = {}

            conn.commit()
            conn.close()

            logger.info("Analytics statistics have been reset")
            return True

        except Exception as e:
            logger.error(f"Error resetting analytics statistics: {e}")
            return False

    def get_summary_stats(self) -> Dict[str, Any]:
        """
        Get summary statistics for the bot

        Returns:
            Dictionary of summary statistics
        """
        try:
            conn = sqlite3.connect(ANALYTICS_DB)
            c = conn.cursor()

            # Get total commands
            c.execute("SELECT COUNT(*) FROM command_usage")
            total_commands = c.fetchone()[0]

            # Get total images
            c.execute("SELECT COUNT(*) FROM image_stats")
            total_images = c.fetchone()[0]

            # Get total unique users
            c.execute(
                """
                SELECT COUNT(DISTINCT user_id) FROM (
                    SELECT user_id FROM command_usage
                    UNION
                    SELECT user_id FROM image_stats
                )
                """
            )
            total_users = c.fetchone()[0]

            # Get average generation time for all generations
            c.execute("SELECT AVG(generation_time) FROM image_stats")
            avg_generation_time = c.fetchone()[0] or 0

            # Get average generation time for images and videos
            # Use try-except to handle the case where is_video column doesn't exist
            try:
                # Get average generation time for images only
                c.execute("SELECT AVG(generation_time) FROM image_stats WHERE is_video = 0")
                avg_image_time = c.fetchone()[0] or 0

                # Get average generation time for videos only
                c.execute("SELECT AVG(generation_time) FROM image_stats WHERE is_video = 1")
                avg_video_time = c.fetchone()[0] or 0
            except sqlite3.OperationalError as e:
                # If the is_video column doesn't exist, use default values
                logger.warning(f"Error getting video/image stats: {e}")
                avg_image_time = avg_generation_time
                avg_video_time = 0.0

            # Get video vs image counts
            try:
                c.execute(
                    """
                    SELECT is_video, COUNT(*) as count
                    FROM image_stats
                    GROUP BY is_video
                    """
                )
                video_counts = {}
                for is_video, count in c.fetchall():
                    if is_video == 1:
                        video_counts["video"] = count
                    else:
                        video_counts["image"] = count

                # If no video counts were found, set defaults
                if "video" not in video_counts:
                    video_counts["video"] = 0
                if "image" not in video_counts:
                    video_counts["image"] = 0
            except sqlite3.OperationalError as e:
                # If the is_video column doesn't exist, use default values
                logger.warning(f"Error getting video/image counts: {e}")
                video_counts = {"video": 0, "image": total_images}

            # Get top commands
            c.execute(
                """
                SELECT command_name, COUNT(*) as count
                FROM command_usage
                GROUP BY command_name
                ORDER BY count DESC
                LIMIT 5
                """
            )
            top_commands = {cmd: cnt for cmd, cnt in c.fetchall()}

            # Get top resolutions
            c.execute(
                """
                SELECT resolution, COUNT(*) as count
                FROM image_stats
                GROUP BY resolution
                ORDER BY count DESC
                LIMIT 5
                """
            )
            top_resolutions = {res: cnt for res, cnt in c.fetchall()}

            # Get top users
            c.execute(
                """
                SELECT user_id, COUNT(*) as count
                FROM (
                    SELECT user_id FROM command_usage
                    UNION ALL
                    SELECT user_id FROM image_stats
                )
                GROUP BY user_id
                ORDER BY count DESC
                LIMIT 5
                """
            )
            top_users = {user: cnt for user, cnt in c.fetchall()}

            conn.close()

            # Calculate uptime
            uptime = time.time() - self.start_time

            return {
                "total_commands": total_commands,
                "total_images": total_images,
                "total_users": total_users,
                "avg_generation_time": avg_generation_time,
                "avg_image_time": avg_image_time,
                "avg_video_time": avg_video_time,
                "top_commands": top_commands,
                "top_resolutions": top_resolutions,
                "top_users": top_users,
                "video_counts": video_counts,
                "uptime": uptime
            }

        except Exception as e:
            logger.error(f"Error getting summary stats: {e}")
            return {}

    def generate_command_chart(self, days: int = 7) -> BytesIO:
        """
        Generate a chart of command usage over time

        Args:
            days: Number of days to include in the chart

        Returns:
            BytesIO object containing the chart image
        """
        try:
            stats = self.get_command_stats(days)

            if not stats:
                raise ValueError("No command stats available")

            dates = [stat["date"] for stat in stats]
            counts = [stat["total_commands"] for stat in stats]

            plt.figure(figsize=(10, 6))
            plt.bar(dates, counts)
            plt.title(f"Command Usage (Last {days} Days)")
            plt.xlabel("Date")
            plt.ylabel("Number of Commands")
            plt.xticks(rotation=45)
            plt.tight_layout()

            # Save to BytesIO
            buf = BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            plt.close()

            return buf

        except Exception as e:
            logger.error(f"Error generating command chart: {e}")
            # Return a simple error image
            plt.figure(figsize=(10, 6))
            plt.text(0.5, 0.5, f"Error generating chart: {str(e)}",
                    horizontalalignment='center', verticalalignment='center')
            plt.axis('off')

            buf = BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            plt.close()

            return buf

    def generate_image_chart(self, days: int = 7) -> BytesIO:
        """
        Generate a chart of image generation over time

        Args:
            days: Number of days to include in the chart

        Returns:
            BytesIO object containing the chart image
        """
        try:
            stats = self.get_image_stats(days)

            if not stats:
                raise ValueError("No image stats available")

            dates = [stat["date"] for stat in stats]
            counts = [stat["total_images"] for stat in stats]
            avg_times = [stat["avg_generation_time"] for stat in stats]

            fig, ax1 = plt.subplots(figsize=(10, 6))

            # Plot image counts
            ax1.bar(dates, counts, color='blue', alpha=0.7)
            ax1.set_xlabel("Date")
            ax1.set_ylabel("Number of Images", color='blue')
            ax1.tick_params(axis='y', labelcolor='blue')
            ax1.set_title(f"Image Generation (Last {days} Days)")

            # Plot average generation time on secondary y-axis
            ax2 = ax1.twinx()
            ax2.plot(dates, avg_times, color='red', marker='o')
            ax2.set_ylabel("Avg Generation Time (s)", color='red')
            ax2.tick_params(axis='y', labelcolor='red')

            plt.xticks(rotation=45)
            plt.tight_layout()

            # Save to BytesIO
            buf = BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            plt.close()

            return buf

        except Exception as e:
            logger.error(f"Error generating image chart: {e}")
            # Return a simple error image
            plt.figure(figsize=(10, 6))
            plt.text(0.5, 0.5, f"Error generating chart: {str(e)}",
                    horizontalalignment='center', verticalalignment='center')
            plt.axis('off')

            buf = BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            plt.close()

            return buf

    def generate_user_chart(self, days: int = 7) -> BytesIO:
        """
        Generate a chart of user activity over time

        Args:
            days: Number of days to include in the chart

        Returns:
            BytesIO object containing the chart image
        """
        try:
            stats = self.get_user_stats(days)

            if not stats:
                raise ValueError("No user stats available")

            dates = [stat["date"] for stat in stats]
            unique_users = [stat["unique_users"] for stat in stats]

            plt.figure(figsize=(10, 6))
            plt.plot(dates, unique_users, marker='o')
            plt.title(f"Unique Users (Last {days} Days)")
            plt.xlabel("Date")
            plt.ylabel("Number of Unique Users")
            plt.xticks(rotation=45)
            plt.tight_layout()

            # Save to BytesIO
            buf = BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            plt.close()

            return buf

        except Exception as e:
            logger.error(f"Error generating user chart: {e}")
            # Return a simple error image
            plt.figure(figsize=(10, 6))
            plt.text(0.5, 0.5, f"Error generating chart: {str(e)}",
                    horizontalalignment='center', verticalalignment='center')
            plt.axis('off')

            buf = BytesIO()
            plt.savefig(buf, format='png')
            buf.seek(0)
            plt.close()

            return buf

    def create_stats_embed(self, bot_name: str) -> discord.Embed:
        """
        Create a Discord embed with bot statistics

        Args:
            bot_name: Name of the bot

        Returns:
            Discord embed with statistics
        """
        stats = self.get_summary_stats()

        if not stats:
            return discord.Embed(
                title=f"{bot_name} Statistics",
                description="No statistics available",
                color=discord.Color.red()
            )

        embed = discord.Embed(
            title=f"{bot_name} Statistics",
            color=discord.Color.blue()
        )

        # Add summary stats
        embed.add_field(
            name="Summary",
            value=f"Total Images: {stats['total_images']}\n"
                 f"Total Users: {stats['total_users']}",
            inline=False
        )

        # Add generation time stats
        generation_time_value = f"All: {stats['avg_generation_time']:.2f}s\n"
        if 'avg_image_time' in stats:
            generation_time_value += f"Images: {stats['avg_image_time']:.2f}s\n"
        if 'avg_video_time' in stats:
            generation_time_value += f"Videos: {stats['avg_video_time']:.2f}s"

        embed.add_field(
            name="Generation Times",
            value=generation_time_value,
            inline=True
        )

        # Top commands section removed as requested

        # Add top resolutions
        if stats['top_resolutions']:
            top_res = "\n".join([f"{res}: {cnt}" for res, cnt in list(stats['top_resolutions'].items())[:3]])
            embed.add_field(
                name="Top Resolutions",
                value=top_res,
                inline=True
            )

        # Add video vs image stats
        if 'video_counts' in stats and stats['video_counts']:
            video_count = stats['video_counts'].get('video', 0)
            image_count = stats['video_counts'].get('image', 0)
            total = video_count + image_count
            video_percent = (video_count / total * 100) if total > 0 else 0
            image_percent = (image_count / total * 100) if total > 0 else 0

            embed.add_field(
                name="Content Types",
                value=f"Videos: {video_count} ({video_percent:.1f}%)\nImages: {image_count} ({image_percent:.1f}%)",
                inline=True
            )

        # Add uptime
        uptime = stats['uptime']
        days = int(uptime // 86400)
        hours = int((uptime % 86400) // 3600)
        minutes = int((uptime % 3600) // 60)

        embed.add_field(
            name="Uptime",
            value=f"{days}d {hours}h {minutes}m",
            inline=True
        )

        # Add timestamp
        embed.timestamp = datetime.datetime.now()

        return embed

# Create a singleton instance
analytics_manager = AnalyticsManager()
