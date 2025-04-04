import discord
from discord import app_commands
from discord.ext import commands
import logging
from typing import Optional, List
import json

from Main.content_filter import content_filter
from config import BOT_MANAGER_ROLE_ID

logger = logging.getLogger(__name__)

def has_filter_admin_permission():
    """Check if the user has filter admin permission"""
    async def predicate(interaction: discord.Interaction) -> bool:
        # Check if user has the bot manager role
        if interaction.user.get_role(BOT_MANAGER_ROLE_ID):
            return True

        # Check if user has administrator permission
        return interaction.user.guild_permissions.administrator

    return app_commands.check(predicate)

async def setup_filter_commands(bot: commands.Bot):
    """Setup content filter commands"""

    @bot.tree.command(name="check_content", description="Check if content violates any filtering rules")
    @has_filter_admin_permission()
    async def check_content(interaction: discord.Interaction, content: str):
        """Check if content violates any filtering rules"""
        try:
            await interaction.response.defer(ephemeral=True)

            is_banned, details = content_filter.check_content(content)

            # Create embed
            if is_banned:
                embed = discord.Embed(
                    title="Content Check Result: ❌ BANNED",
                    description=f"The provided content violates one or more filtering rules.",
                    color=discord.Color.red()
                )
            else:
                embed = discord.Embed(
                    title="Content Check Result: ✅ ALLOWED",
                    description=f"The provided content does not violate any filtering rules.",
                    color=discord.Color.green()
                )

            # Add banned words
            if details['banned_words']:
                embed.add_field(
                    name="Banned Words",
                    value=", ".join(details['banned_words']),
                    inline=False
                )

            # Add regex matches
            if details['regex_matches']:
                regex_text = ""
                for match in details['regex_matches']:
                    regex_text += f"**{match['name']}** ({match['severity']}): {', '.join(match['matches'])}\n"

                embed.add_field(
                    name="Regex Pattern Matches",
                    value=regex_text,
                    inline=False
                )

            # Add context violations
            if details['context_violations']:
                context_text = ""
                for violation in details['context_violations']:
                    if 'disallowed_context' in violation:
                        context_text += f"**{violation['trigger_word']}** in disallowed context: '{violation['disallowed_context']}'\n"
                    elif 'missing_allowed_context' in violation:
                        context_text += f"**{violation['trigger_word']}** without allowed context\n"

                embed.add_field(
                    name="Context Violations",
                    value=context_text,
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in check_content command: {e}")
            await interaction.followup.send("An error occurred while checking content.", ephemeral=True)

    @bot.tree.command(name="filter_add_word", description="Add a word to the content filter banned words list")
    @has_filter_admin_permission()
    async def filter_add_word(interaction: discord.Interaction, word: str):
        """Add a word to the banned words list"""
        try:
            await interaction.response.defer(ephemeral=True)

            success = content_filter.add_banned_word(word)

            if success:
                await interaction.followup.send(f"Added '{word}' to the banned words list.", ephemeral=True)
            else:
                await interaction.followup.send(f"Failed to add '{word}' to the banned words list.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error in filter_add_word command: {e}")
            await interaction.followup.send("An error occurred while adding word to content filter.", ephemeral=True)

    @bot.tree.command(name="filter_remove_word", description="Remove a word from the content filter banned words list")
    @has_filter_admin_permission()
    async def filter_remove_word(interaction: discord.Interaction, word: str):
        """Remove a word from the banned words list"""
        try:
            await interaction.response.defer(ephemeral=True)

            success = content_filter.remove_banned_word(word)

            if success:
                await interaction.followup.send(f"Removed '{word}' from the banned words list.", ephemeral=True)
            else:
                await interaction.followup.send(f"Failed to remove '{word}' from the banned words list.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error in filter_remove_word command: {e}")
            await interaction.followup.send("An error occurred while removing word from content filter.", ephemeral=True)

    @bot.tree.command(name="filter_list_words", description="List all words in the content filter banned words list")
    @has_filter_admin_permission()
    async def filter_list_words(interaction: discord.Interaction):
        """List all banned words"""
        try:
            await interaction.response.defer(ephemeral=True)

            banned_words = sorted(list(content_filter.banned_words))

            if not banned_words:
                await interaction.followup.send("There are no banned words.", ephemeral=True)
                return

            # Split into chunks of 20 words
            chunks = [banned_words[i:i+20] for i in range(0, len(banned_words), 20)]

            # Create embed
            embed = discord.Embed(
                title=f"Banned Words ({len(banned_words)} total)",
                color=discord.Color.blue()
            )

            for i, chunk in enumerate(chunks[:10]):  # Show up to 10 chunks (200 words)
                embed.add_field(
                    name=f"Words {i*20+1}-{i*20+len(chunk)}",
                    value=", ".join(chunk),
                    inline=False
                )

            if len(chunks) > 10:
                embed.set_footer(text=f"Showing 200 of {len(banned_words)} words")

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in filter_list_words command: {e}")
            await interaction.followup.send("An error occurred while listing content filter words.", ephemeral=True)

    @bot.tree.command(name="add_regex_pattern", description="Add a regex pattern to the content filter")
    @has_filter_admin_permission()
    @app_commands.choices(severity=[
        app_commands.Choice(name="Low", value="low"),
        app_commands.Choice(name="Medium", value="medium"),
        app_commands.Choice(name="High", value="high")
    ])
    async def add_regex_pattern(
        interaction: discord.Interaction,
        name: str,
        pattern: str,
        description: str = "",
        severity: str = "medium"
    ):
        """Add a regex pattern to the content filter"""
        try:
            await interaction.response.defer(ephemeral=True)

            success = content_filter.add_regex_pattern(
                name=name,
                pattern=pattern,
                description=description,
                severity=severity.value
            )

            if success:
                await interaction.followup.send(f"Added regex pattern '{name}' to the content filter.", ephemeral=True)
            else:
                await interaction.followup.send(f"Failed to add regex pattern '{name}' to the content filter.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error in add_regex_pattern command: {e}")
            await interaction.followup.send("An error occurred while adding regex pattern.", ephemeral=True)

    @bot.tree.command(name="remove_regex_pattern", description="Remove a regex pattern from the content filter")
    @has_filter_admin_permission()
    async def remove_regex_pattern(interaction: discord.Interaction, name: str):
        """Remove a regex pattern from the content filter"""
        try:
            await interaction.response.defer(ephemeral=True)

            success = content_filter.remove_regex_pattern(name)

            if success:
                await interaction.followup.send(f"Removed regex pattern '{name}' from the content filter.", ephemeral=True)
            else:
                await interaction.followup.send(f"Failed to remove regex pattern '{name}' from the content filter.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error in remove_regex_pattern command: {e}")
            await interaction.followup.send("An error occurred while removing regex pattern.", ephemeral=True)

    @bot.tree.command(name="list_regex_patterns", description="List all regex patterns in the content filter")
    @has_filter_admin_permission()
    async def list_regex_patterns(interaction: discord.Interaction):
        """List all regex patterns in the content filter"""
        try:
            await interaction.response.defer(ephemeral=True)

            patterns = content_filter.regex_patterns

            if not patterns:
                await interaction.followup.send("There are no regex patterns.", ephemeral=True)
                return

            # Create embed
            embed = discord.Embed(
                title=f"Regex Patterns ({len(patterns)} total)",
                color=discord.Color.blue()
            )

            for pattern in patterns:
                pattern_str = pattern['pattern'].pattern if hasattr(pattern['pattern'], 'pattern') else str(pattern['pattern'])
                embed.add_field(
                    name=f"{pattern['name']} ({pattern['severity']})",
                    value=f"Pattern: `{pattern_str}`\nDescription: {pattern['description']}",
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in list_regex_patterns command: {e}")
            await interaction.followup.send("An error occurred while listing regex patterns.", ephemeral=True)

    @bot.tree.command(name="add_context_rule", description="Add a context rule to the content filter")
    @has_filter_admin_permission()
    async def add_context_rule(
        interaction: discord.Interaction,
        trigger_word: str,
        allowed_contexts: str = "",
        disallowed_contexts: str = "",
        description: str = ""
    ):
        """Add a context rule to the content filter"""
        try:
            await interaction.response.defer(ephemeral=True)

            # Parse contexts
            allowed_list = [ctx.strip() for ctx in allowed_contexts.split(',') if ctx.strip()] if allowed_contexts else []
            disallowed_list = [ctx.strip() for ctx in disallowed_contexts.split(',') if ctx.strip()] if disallowed_contexts else []

            if not allowed_list and not disallowed_list:
                await interaction.followup.send("You must provide at least one allowed or disallowed context.", ephemeral=True)
                return

            success = content_filter.add_context_rule(
                trigger_word=trigger_word,
                allowed_contexts=allowed_list,
                disallowed_contexts=disallowed_list,
                description=description
            )

            if success:
                await interaction.followup.send(f"Added context rule for '{trigger_word}' to the content filter.", ephemeral=True)
            else:
                await interaction.followup.send(f"Failed to add context rule for '{trigger_word}' to the content filter.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error in add_context_rule command: {e}")
            await interaction.followup.send("An error occurred while adding context rule.", ephemeral=True)

    @bot.tree.command(name="remove_context_rule", description="Remove a context rule from the content filter")
    @has_filter_admin_permission()
    async def remove_context_rule(interaction: discord.Interaction, trigger_word: str):
        """Remove a context rule from the content filter"""
        try:
            await interaction.response.defer(ephemeral=True)

            success = content_filter.remove_context_rule(trigger_word)

            if success:
                await interaction.followup.send(f"Removed context rule for '{trigger_word}' from the content filter.", ephemeral=True)
            else:
                await interaction.followup.send(f"Failed to remove context rule for '{trigger_word}' from the content filter.", ephemeral=True)

        except Exception as e:
            logger.error(f"Error in remove_context_rule command: {e}")
            await interaction.followup.send("An error occurred while removing context rule.", ephemeral=True)

    @bot.tree.command(name="list_context_rules", description="List all context rules in the content filter")
    @has_filter_admin_permission()
    async def list_context_rules(interaction: discord.Interaction):
        """List all context rules in the content filter"""
        try:
            await interaction.response.defer(ephemeral=True)

            rules = content_filter.context_rules

            if not rules:
                await interaction.followup.send("There are no context rules.", ephemeral=True)
                return

            # Create embed
            embed = discord.Embed(
                title=f"Context Rules ({len(rules)} total)",
                color=discord.Color.blue()
            )

            for rule in rules:
                allowed = ", ".join(rule.get('allowed_contexts', [])) or "None"
                disallowed = ", ".join(rule.get('disallowed_contexts', [])) or "None"

                embed.add_field(
                    name=f"Trigger Word: {rule['trigger_word']}",
                    value=f"Allowed Contexts: {allowed}\nDisallowed Contexts: {disallowed}\nDescription: {rule.get('description', '')}",
                    inline=False
                )

            await interaction.followup.send(embed=embed, ephemeral=True)

        except Exception as e:
            logger.error(f"Error in list_context_rules command: {e}")
            await interaction.followup.send("An error occurred while listing context rules.", ephemeral=True)
