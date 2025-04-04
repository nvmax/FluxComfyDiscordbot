import discord
from discord import app_commands
from discord.ext import commands
import logging
import asyncio
from typing import Optional, Dict, Any, List
import time
import datetime
import functools

from Main.analytics import analytics_manager
from config import BOT_MANAGER_ROLE_ID

logger = logging.getLogger(__name__)

def has_analytics_permission():
    """Check if the user has analytics permission"""
    async def predicate(interaction: discord.Interaction) -> bool:
        # Check if user has the bot manager role
        if interaction.user.get_role(BOT_MANAGER_ROLE_ID):
            return True

        # Check if user has administrator permission
        return interaction.user.guild_permissions.administrator

    return app_commands.check(predicate)

def track_command_usage(func):
    """Decorator to track command usage"""
    @functools.wraps(func)
    async def wrapper(interaction: discord.Interaction, *args, **kwargs):
        command_name = interaction.command.name if interaction.command else "unknown"
        start_time = time.time()

        try:
            await func(interaction, *args, **kwargs)
            success = True
        except Exception as e:
            success = False
            raise
        finally:
            execution_time = time.time() - start_time
            analytics_manager.track_command(
                command_name=command_name,
                user_id=str(interaction.user.id),
                guild_id=str(interaction.guild.id) if interaction.guild else None,
                channel_id=str(interaction.channel.id) if interaction.channel else None,
                execution_time=execution_time,
                success=success
            )

    return wrapper

async def setup_analytics_commands(bot: commands.Bot):
    """Setup analytics-related commands"""

    @bot.tree.command(name="reset_stats", description="Reset all analytics statistics")
    @has_analytics_permission()
    @track_command_usage
    async def reset_stats(interaction: discord.Interaction, confirm: bool = False):
        """Reset all analytics statistics (admin only)"""
        try:
            await interaction.response.defer(ephemeral=True)

            if not confirm:
                await interaction.followup.send(
                    "⚠️ This will delete ALL analytics data. This action cannot be undone. "
                    "Run the command again with `confirm=True` to proceed.",
                    ephemeral=True
                )
                return

            # Reset the analytics database
            analytics_manager.reset_stats()

            await interaction.followup.send("✅ All analytics statistics have been reset.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error in reset_stats command: {e}")
            await interaction.followup.send("An error occurred while resetting statistics.", ephemeral=True)

    @bot.tree.command(name="stats", description="View bot statistics")
    @track_command_usage
    async def stats(interaction: discord.Interaction):
        """Show bot statistics"""
        try:
            await interaction.response.defer(ephemeral=True)

            # Create stats embed
            embed = analytics_manager.create_stats_embed(bot.user.name)

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in stats command: {e}")
            await interaction.followup.send("An error occurred while getting statistics.", ephemeral=True)

    @bot.tree.command(name="command_stats", description="View command usage statistics")
    @has_analytics_permission()
    @track_command_usage
    async def command_stats(interaction: discord.Interaction, days: int = 7):
        """Show command usage statistics"""
        try:
            await interaction.response.defer(ephemeral=True)

            # Get command stats
            stats = analytics_manager.get_command_stats(days)

            if not stats:
                await interaction.followup.send("No command statistics available.", ephemeral=True)
                return

            # Create embed
            embed = discord.Embed(
                title=f"Command Usage Statistics (Last {days} Days)",
                color=discord.Color.blue()
            )

            # Add total commands per day
            total_commands = sum(stat["total_commands"] for stat in stats)
            daily_avg = total_commands / len(stats) if stats else 0

            embed.add_field(
                name="Summary",
                value=f"Total Commands: {total_commands}\nDaily Average: {daily_avg:.1f}",
                inline=False
            )

            # Add breakdown by day
            for stat in stats[-5:]:  # Show last 5 days
                date = stat["date"]
                count = stat["total_commands"]

                # Get top commands for this day
                top_cmds = "\n".join([f"{cmd}: {cnt}" for cmd, cnt in list(stat["command_breakdown"].items())[:3]])
                if not top_cmds:
                    top_cmds = "None"

                embed.add_field(
                    name=f"{date} ({count} commands)",
                    value=f"Top Commands:\n{top_cmds}",
                    inline=True
                )

            # Generate and attach chart
            chart = await asyncio.to_thread(analytics_manager.generate_command_chart, days)
            file = discord.File(chart, filename="command_stats.png")
            embed.set_image(url="attachment://command_stats.png")

            await interaction.followup.send(embed=embed, file=file, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in command_stats command: {e}")
            await interaction.followup.send("An error occurred while getting command statistics.", ephemeral=True)

    @bot.tree.command(name="image_stats", description="View image generation statistics")
    @has_analytics_permission()
    @track_command_usage
    async def image_stats(interaction: discord.Interaction, days: int = 7):
        """Show image generation statistics"""
        try:
            await interaction.response.defer(ephemeral=True)

            # Get image stats
            stats = analytics_manager.get_image_stats(days)

            if not stats:
                await interaction.followup.send("No image statistics available.", ephemeral=True)
                return

            # Create embed
            embed = discord.Embed(
                title=f"Image Generation Statistics (Last {days} Days)",
                color=discord.Color.blue()
            )

            # Add total images per day
            total_images = sum(stat["total_images"] for stat in stats)
            daily_avg = total_images / len(stats) if stats else 0
            avg_gen_time = sum(stat["avg_generation_time"] for stat in stats) / len(stats) if stats else 0
            avg_image_time = sum(stat.get("avg_image_time", 0) for stat in stats) / len(stats) if stats else 0
            avg_video_time = sum(stat.get("avg_video_time", 0) for stat in stats) / len(stats) if stats else 0

            embed.add_field(
                name="Summary",
                value=f"Total Images: {total_images}\nDaily Average: {daily_avg:.1f}\nAvg Generation Time: {avg_gen_time:.2f}s",
                inline=False
            )

            # Add generation time breakdown
            embed.add_field(
                name="Generation Times",
                value=f"All: {avg_gen_time:.2f}s\nImages: {avg_image_time:.2f}s\nVideos: {avg_video_time:.2f}s",
                inline=False
            )

            # Add breakdown by day
            for stat in stats[-5:]:  # Show last 5 days
                date = stat["date"]
                count = stat["total_images"]
                avg_time = stat["avg_generation_time"]

                # Get top resolutions for this day
                top_res = "\n".join([f"{res}: {cnt}" for res, cnt in list(stat["resolution_breakdown"].items())[:3]])
                if not top_res:
                    top_res = "None"

                # Get video vs image breakdown
                video_stats = ""
                if "video_breakdown" in stat and stat["video_breakdown"]:
                    video_count = stat["video_breakdown"].get("video", 0)
                    image_count = stat["video_breakdown"].get("image", 0)
                    video_stats = f"Videos: {video_count}\nImages: {image_count}"

                # Get generation type breakdown for this day
                type_breakdown = "\n".join([f"{typ}: {cnt}" for typ, cnt in list(stat["type_breakdown"].items())])
                if not type_breakdown:
                    type_breakdown = "None"

                embed.add_field(
                    name=f"{date} ({count} images)",
                    value=f"Avg Time: {avg_time:.2f}s\nImg Time: {stat.get('avg_image_time', 0):.2f}s\nVid Time: {stat.get('avg_video_time', 0):.2f}s\nTop Resolutions:\n{top_res}\n{video_stats}\nGeneration Types:\n{type_breakdown}",
                    inline=True
                )

            # Generate and attach chart
            chart = await asyncio.to_thread(analytics_manager.generate_image_chart, days)
            file = discord.File(chart, filename="image_stats.png")
            embed.set_image(url="attachment://image_stats.png")

            await interaction.followup.send(embed=embed, file=file, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in image_stats command: {e}")
            await interaction.followup.send("An error occurred while getting image statistics.", ephemeral=True)

    @bot.tree.command(name="user_stats", description="View user activity statistics")
    @has_analytics_permission()
    @track_command_usage
    async def user_stats(interaction: discord.Interaction, days: int = 7):
        """Show user activity statistics"""
        try:
            await interaction.response.defer(ephemeral=True)

            # Get user stats
            stats = analytics_manager.get_user_stats(days)

            if not stats:
                await interaction.followup.send("No user statistics available.", ephemeral=True)
                return

            # Create embed
            embed = discord.Embed(
                title=f"User Activity Statistics (Last {days} Days)",
                color=discord.Color.blue()
            )

            # Add total unique users
            total_unique = sum(stat["unique_users"] for stat in stats) / len(stats) if stats else 0

            embed.add_field(
                name="Summary",
                value=f"Average Daily Users: {total_unique:.1f}",
                inline=False
            )

            # Add breakdown by day
            for stat in stats[-5:]:  # Show last 5 days
                date = stat["date"]
                unique = stat["unique_users"]

                # Get top users for this day
                top_users_list = []
                for user_id, count in list(stat["top_users"].items())[:3]:
                    user = interaction.guild.get_member(int(user_id)) if interaction.guild else None
                    name = user.display_name if user else f"User {user_id}"
                    top_users_list.append(f"{name}: {count}")

                top_users = "\n".join(top_users_list) if top_users_list else "None"

                embed.add_field(
                    name=f"{date} ({unique} users)",
                    value=f"Top Users:\n{top_users}",
                    inline=True
                )

            # Generate and attach chart
            chart = await asyncio.to_thread(analytics_manager.generate_user_chart, days)
            file = discord.File(chart, filename="user_stats.png")
            embed.set_image(url="attachment://user_stats.png")

            await interaction.followup.send(embed=embed, file=file, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in user_stats command: {e}")
            await interaction.followup.send("An error occurred while getting user statistics.", ephemeral=True)
