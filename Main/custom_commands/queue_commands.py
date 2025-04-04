import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio
from typing import Optional, Dict, Any, List
import time

from Main.queue_system import QueuePriority, QueueStatus
from Main.utils import format_time_delta
from config import BOT_MANAGER_ROLE_ID

logger = logging.getLogger(__name__)

def has_queue_admin_permission():
    """Check if the user has queue admin permission"""
    async def predicate(interaction: discord.Interaction) -> bool:
        # Check if user has the bot manager role
        if interaction.user.get_role(BOT_MANAGER_ROLE_ID):
            return True

        # Check if user has administrator permission
        return interaction.user.guild_permissions.administrator

    return app_commands.check(predicate)

async def setup_queue_commands(bot: commands.Bot):
    """Setup queue-related commands"""

    @bot.tree.command(name="queue_status", description="Check the status of the image generation queue")
    async def queue_status(interaction: discord.Interaction):
        """Show the current status of the image generation queue"""
        try:
            await interaction.response.defer(ephemeral=True)

            # Get queue status
            status = bot.image_queue.get_queue_status()

            # Create embed
            embed = discord.Embed(
                title="Image Generation Queue Status",
                color=discord.Color.blue()
            )

            embed.add_field(name="Queue Size", value=status["queue_size"], inline=True)
            embed.add_field(name="Processing", value=status["processing"], inline=True)
            embed.add_field(name="Max Concurrent", value=status["max_concurrent"], inline=True)

            # Get user's position in queue
            user_items = bot.image_queue.get_user_queue_items(str(interaction.user.id))
            pending_items = [item for item in user_items if item["status"] == QueueStatus.PENDING]

            if pending_items:
                embed.add_field(
                    name="Your Pending Requests",
                    value=len(pending_items),
                    inline=False
                )

                # Show details of the first few pending items
                for i, item in enumerate(pending_items[:3]):
                    added_time = time.time() - item["added_at"]
                    embed.add_field(
                        name=f"Request {i+1}",
                        value=f"Added: {format_time_delta(added_time)} ago\nType: {item['request_type']}",
                        inline=True
                    )

            # Add queue stats
            stats = bot.image_queue.get_queue_stats(1)  # Get today's stats
            if stats:
                today_stats = stats[0]
                embed.add_field(
                    name="Today's Stats",
                    value=f"Total: {today_stats['total_requests']}\nCompleted: {today_stats['completed_requests']}\nFailed: {today_stats['failed_requests']}",
                    inline=False
                )

                # Add average processing time
                avg_time = today_stats["avg_processing_time"]
                embed.add_field(
                    name="Avg. Processing Time",
                    value=format_time_delta(avg_time),
                    inline=True
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in queue_status command: {e}")
            await interaction.followup.send("An error occurred while getting queue status.", ephemeral=True)

    @bot.tree.command(name="my_requests", description="View your pending and recent image generation requests")
    async def my_requests(interaction: discord.Interaction):
        """Show the user's pending and recent requests"""
        try:
            await interaction.response.defer(ephemeral=True)

            # Get user's queue items
            user_items = bot.image_queue.get_user_queue_items(str(interaction.user.id))

            if not user_items:
                await interaction.followup.send("You don't have any pending or recent requests.", ephemeral=True)
                return

            # Create embed
            embed = discord.Embed(
                title="Your Image Generation Requests",
                color=discord.Color.blue()
            )

            # Group by status
            pending = [item for item in user_items if item["status"] == QueueStatus.PENDING]
            processing = [item for item in user_items if item["status"] == QueueStatus.PROCESSING]
            completed = [item for item in user_items if item["status"] == QueueStatus.COMPLETED]
            failed = [item for item in user_items if item["status"] == QueueStatus.FAILED]

            # Add summary
            embed.add_field(
                name="Summary",
                value=f"Pending: {len(pending)}\nProcessing: {len(processing)}\nCompleted: {len(completed)}\nFailed: {len(failed)}",
                inline=False
            )

            # Add pending requests
            if pending:
                pending_text = ""
                for i, item in enumerate(pending[:5]):  # Show up to 5
                    added_time = time.time() - item["added_at"]
                    pending_text += f"{i+1}. Added {format_time_delta(added_time)} ago - {item['request_type']}\n"

                if len(pending) > 5:
                    pending_text += f"...and {len(pending) - 5} more\n"

                embed.add_field(
                    name="Pending Requests",
                    value=pending_text,
                    inline=False
                )

            # Add processing requests
            if processing:
                processing_text = ""
                for i, item in enumerate(processing[:3]):  # Show up to 3
                    started_time = time.time() - item["started_at"]
                    processing_text += f"{i+1}. Processing for {format_time_delta(started_time)} - {item['request_type']}\n"

                embed.add_field(
                    name="Processing Requests",
                    value=processing_text,
                    inline=False
                )

            # Add recent completed requests
            if completed:
                completed_text = ""
                for i, item in enumerate(completed[:3]):  # Show up to 3
                    completed_time = time.time() - item["completed_at"]
                    completed_text += f"{i+1}. Completed {format_time_delta(completed_time)} ago - {item['request_type']}\n"

                embed.add_field(
                    name="Recent Completed Requests",
                    value=completed_text,
                    inline=False
                )

            # Create a view with or without the cancel button
            try:
                # Always create a view, but only add items if there are pending requests
                view = discord.ui.View(timeout=60)

                # Add cancel button for pending requests
                if pending:
                    try:
                        select_menu = QueueRequestSelect(pending)
                        view.add_item(select_menu)
                    except Exception as e:
                        logger.error(f"Error creating select menu: {e}")
                        # Continue with an empty view if there's an error

                # Send the response with the view
                await interaction.followup.send(embed=embed, view=view, ephemeral=True)
            except Exception as e:
                logger.error(f"Error creating view: {e}")
                # As a last resort, try sending without a view
                await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in my_requests command: {e}")
            await interaction.followup.send("An error occurred while getting your requests.", ephemeral=True)

    @bot.tree.command(name="queue_stats", description="View queue statistics")
    @has_queue_admin_permission()
    async def queue_stats(interaction: discord.Interaction, days: int = 7):
        """Show queue statistics for admins"""
        try:
            await interaction.response.defer(ephemeral=True)

            # Get queue stats
            stats = bot.image_queue.get_queue_stats(days)

            if not stats:
                await interaction.followup.send("No queue statistics available.", ephemeral=True)
                return

            # Create embed
            embed = discord.Embed(
                title=f"Queue Statistics (Last {len(stats)} Days)",
                color=discord.Color.blue()
            )

            # Add stats for each day
            for day_stats in stats:
                date = day_stats["date"]
                total = day_stats["total_requests"]
                completed = day_stats["completed_requests"]
                failed = day_stats["failed_requests"]
                avg_time = day_stats["avg_processing_time"]

                success_rate = (completed / total) * 100 if total > 0 else 0

                embed.add_field(
                    name=date,
                    value=f"Total: {total}\nCompleted: {completed}\nFailed: {failed}\nSuccess Rate: {success_rate:.1f}%\nAvg Time: {format_time_delta(avg_time)}",
                    inline=True
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in queue_stats command: {e}")
            await interaction.followup.send("An error occurred while getting queue statistics.", ephemeral=True)

    @bot.tree.command(name="set_queue_priority", description="Set the priority for a user's requests")
    @has_queue_admin_permission()
    @app_commands.choices(priority=[
        app_commands.Choice(name="High", value=QueuePriority.HIGH),
        app_commands.Choice(name="Normal", value=QueuePriority.NORMAL),
        app_commands.Choice(name="Low", value=QueuePriority.LOW)
    ])
    async def set_queue_priority(
        interaction: discord.Interaction,
        user: discord.User,
        priority: int = QueuePriority.NORMAL
    ):
        """Set the priority for a user's requests (admin only)"""
        try:
            await interaction.response.defer(ephemeral=True)

            # Store the priority in the bot for future requests
            if not hasattr(bot, "user_priorities"):
                bot.user_priorities = {}

            bot.user_priorities[str(user.id)] = priority.value

            priority_names = {
                QueuePriority.HIGH: "High",
                QueuePriority.NORMAL: "Normal",
                QueuePriority.LOW: "Low"
            }

            await interaction.followup.send(
                f"Set priority for {user.display_name} to {priority_names[priority.value]}.",
                ephemeral=True
            )

        except Exception as e:
            logger.error(f"Error in set_queue_priority command: {e}")
            await interaction.followup.send("An error occurred while setting queue priority.", ephemeral=True)

# Note: This class is no longer used directly, but kept for reference
# class QueueRequestsView(discord.ui.View):
#     """View for managing queue requests"""
#
#     def __init__(self, bot, pending_items, user_id):
#         super().__init__(timeout=60)
#         self.bot = bot
#         self.pending_items = pending_items
#         self.user_id = user_id
#
#         # Add select menu for pending requests if there are any
#         if pending_items:
#             try:
#                 select_menu = QueueRequestSelect(pending_items)
#                 self.add_item(select_menu)
#             except Exception as e:
#                 logger.error(f"Error creating select menu: {e}")
#
#     async def on_timeout(self):
#         """Handle timeout"""
#         # Clear all items
#         self.clear_items()

class QueueRequestSelect(discord.ui.Select):
    """Select menu for queue requests"""

    def __init__(self, pending_items):
        options = []

        # Add options for each pending request (up to 25, which is the Discord limit)
        for i, item in enumerate(pending_items[:25]):
            request_id = item["request_id"]
            request_type = item["request_type"]
            added_time = time.time() - item["added_at"]

            option = discord.SelectOption(
                label=f"Request {i+1} ({request_type})",
                description=f"Added {format_time_delta(added_time)} ago",
                value=request_id
            )
            options.append(option)

        # Ensure we have at least one option
        if not options:
            raise ValueError("No pending requests to create options for")

        super().__init__(
            placeholder="Select a request to cancel...",
            min_values=1,
            max_values=1,
            options=options
        )

    async def callback(self, interaction: discord.Interaction):
        """Handle selection"""
        request_id = self.values[0]

        # Cancel the request
        success = await interaction.client.image_queue.cancel_request(
            request_id,
            str(interaction.user.id)
        )

        if success:
            await interaction.response.send_message(
                "Request cancelled successfully.",
                ephemeral=True
            )
        else:
            await interaction.response.send_message(
                "Failed to cancel request. It may have already been processed.",
                ephemeral=True
            )
