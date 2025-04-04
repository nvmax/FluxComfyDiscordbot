import discord
from aiohttp import web
import logging
import json
import io
import time
from Main.database import add_to_history
from Main.utils import load_json
from .models import RequestItem, ReduxRequestItem, ReduxPromptRequestItem
from typing import Dict, Any
import asyncio
from .message_constants import STATUS_MESSAGES
from .views import ImageControlView, ReduxImageView, PuLIDImageView
from config import fluxversion

# Import analytics manager if available
try:
    from Main.analytics import analytics_manager
    ANALYTICS_ENABLED = True
except ImportError:
    ANALYTICS_ENABLED = False
    print("Analytics module not found. Analytics tracking disabled.")

logger = logging.getLogger(__name__)

async def handle_generated_image(request):
    try:
        request_data = {}

        # Process the multipart form data
        reader = await request.multipart()

        while True:
            part = await reader.next()
            if part is None:
                break

            if part.name in ['video_data', 'image_data']:
                # Handle binary data (video or image)
                request_data[part.name] = await part.read()
            else:
                # Handle text data
                request_data[part.name] = await part.text()

        # Log all received data fields for debugging
        logger.debug(f"Received data fields: {list(request_data.keys())}")
        if 'generation_time' in request_data:
            logger.debug(f"Received generation_time: {request_data['generation_time']}")

        # Convert string 'True'/'False' to boolean
        is_video = request_data.get('is_video', 'False').lower() == 'true'

        # Get the channel where we need to send the response
        channel_id = int(request_data['channel_id'])
        channel = request.app['bot'].get_channel(channel_id)

        if not channel:
            logger.error(f"Could not find channel with ID {channel_id}")
            return web.Response(status=404, text="Channel not found")

        # Prepare the file to send
        if is_video:
            file = discord.File(io.BytesIO(request_data['video_data']), filename='output.mp4')
        else:
            file = discord.File(io.BytesIO(request_data['image_data']), filename='output.png')

        # Handle seed value - convert to int only if it's not None or 'None'
        seed_value = request_data.get('seed')
        if seed_value and seed_value.lower() != 'none':
            try:
                seed_value = int(seed_value)
            except ValueError:
                seed_value = None
        else:
            seed_value = None

        # Create the appropriate view based on content type
        if is_video:
            view = ReduxImageView()  # ReduxImageView only has a delete button
        else:
            view = ImageControlView(
                request.app['bot'],
                original_prompt=request_data['prompt'],
                image_filename='output.png',
                original_resolution=request_data['resolution'],
                original_loras=json.loads(request_data['loras']),
                original_upscale_factor=int(request_data['upscale_factor']),
                original_seed=seed_value
            )

        # Create embed for the prompt
        try:
            # Try to get member through fetch_member for more reliable role info
            user = await channel.guild.fetch_member(int(request_data['user_id'])) if channel.guild else None

            # Get the highest colored role
            colored_role = None
            if user:
                for role in reversed(user.roles):
                    if role.color.value != 0:
                        colored_role = role
                        break

            embed_color = colored_role.color if colored_role else discord.Color.blurple()

        except (discord.NotFound, discord.HTTPException):
            # Fallback to blurple if we can't get the user or their roles
            embed_color = discord.Color.blurple()

        embed = discord.Embed(color=embed_color)
        embed.description = f"🎨 {request_data['prompt']}\n\n" \
                          f"📏 Resolution: {request_data['resolution']}\n" \
                          f"🔍 Upscale: {request_data['upscale_factor']}x\n" \
                          f"🎲 Seed: {seed_value}\n" \
                          f"📚 LoRAs: {', '.join(json.loads(request_data['loras'])) if json.loads(request_data['loras']) else 'None'}"
        embed.set_author(name=f"Image generated for {user.display_name if user else 'Unknown User'}")

        # Add to history database and analytics
        try:
            user_id = request_data['user_id']
            prompt = request_data['prompt']
            workflow = json.loads(request_data.get('workflow', '{}'))
            resolution = request_data['resolution']
            loras = json.loads(request_data['loras'])
            upscale_factor = int(request_data['upscale_factor'])

            add_to_history(user_id, prompt, workflow, 'output.png', resolution, loras, upscale_factor)

            # Track analytics if enabled
            if ANALYTICS_ENABLED:
                # Get generation time if available
                generation_time = 0.0  # Default if not available
                if 'generation_time' in request_data and request_data['generation_time']:
                    try:
                        generation_time = float(request_data['generation_time'])
                        logger.info(f"Received generation time: {generation_time:.2f} seconds")
                    except (ValueError, TypeError) as e:
                        logger.error(f"Error parsing generation time: {e}")

                # Determine if this is a video
                is_video = False
                if 'is_video' in request_data and request_data['is_video'].lower() == 'true':
                    is_video = True
                    logger.info("Detected video generation")
                elif 'request_type' in request_data and request_data['request_type'].lower() == 'video':
                    is_video = True
                    logger.info("Detected video generation from request_type")

                # Track the image generation
                analytics_manager.track_image_generation(
                    user_id=user_id,
                    prompt=prompt,
                    resolution=resolution,
                    loras=loras,
                    upscale_factor=upscale_factor,
                    generation_time=generation_time,
                    is_video=is_video
                )
        except Exception as e:
            logger.error(f"Error adding to history or analytics: {str(e)}")

        # Get the original progress message and update it
        try:
            progress_message = await channel.fetch_message(int(request_data['original_message_id']))
            await progress_message.edit(content=None, embed=embed, attachments=[], view=view)
            await progress_message.add_files(file)
        except (discord.NotFound, discord.HTTPException) as e:
            # If we can't find the original message or there's an error editing, send as new message
            logger.error(f"Could not edit original message, sending new one: {str(e)}")
            await channel.send(file=file, embed=embed, view=view)

        return web.Response(text="Success")

    except Exception as e:
        logger.error(f"Error in handle_generated_image: {str(e)}", exc_info=True)
        return web.Response(status=500, text=f"Internal server error: {str(e)}")

async def update_progress(request):
    try:
        data = await request.json()
        request_id = data.get('request_id')
        progress_data = data.get('progress_data', {})

        if not request_id:
            return web.Response(text="Missing request_id", status=400)

        if request_id not in request.app['bot'].pending_requests:
            return web.Response(text="Unknown request_id", status=404)

        request_item = request.app['bot'].pending_requests[request_id]
        await update_progress_message(request.app['bot'], request_item, progress_data)

        return web.Response(text="Progress updated")
    except Exception as e:
        logger.error(f"Error in update_progress: {str(e)}", exc_info=True)
        return web.Response(text="Internal server error", status=500)

async def update_progress_message(bot, request_item, progress_data: Dict[str, Any]):
    try:
        channel = await bot.fetch_channel(int(request_item.channel_id))
        message = await channel.fetch_message(int(request_item.original_message_id))

        status = progress_data.get('status', '')
        progress_message = progress_data.get('message', 'Processing...')
        progress = progress_data.get('progress', 0)

        # Get the status info from our mapping
        status_info = STATUS_MESSAGES.get(status, {
            'message': progress_message,
            'emoji': '⚙️'  # Default emoji for unknown status
        })

        # Format message based on status
        if status == 'generating':
            formatted_message = f"{status_info['emoji']} {status_info['message']} {progress}%"
        elif status == 'error':
            formatted_message = f"{status_info['emoji']} {status_info['message']} {progress_message}"
        else:
            formatted_message = f"{status_info['emoji']} {status_info['message']}"

        await message.edit(content=formatted_message)
        logger.debug(f"Updated progress message: {formatted_message}")

    except discord.errors.NotFound:
        logger.warning(f"Message {request_item.original_message_id} not found")
    except discord.errors.Forbidden:
        logger.warning("Bot lacks permission to edit message")
    except Exception as e:
        logger.error(f"Error updating progress message: {str(e)}")

async def check_timeout(bot, request_id: str, timeout: int = 300):
    """
    Monitor request for timeout
    """
    try:
        await asyncio.sleep(timeout)
        if request_id in bot.pending_requests:
            request_item = bot.pending_requests[request_id]
            try:
                channel = await bot.fetch_channel(int(request_item.channel_id))
                message = await channel.fetch_message(int(request_item.original_message_id))
                await message.edit(content="⚠️ Generation timed out after 5 minutes")
            except Exception as e:
                logger.error(f"Error handling timeout: {str(e)}")
            finally:
                del bot.pending_requests[request_id]
    except Exception as e:
        logger.error(f"Error in timeout checker: {str(e)}")