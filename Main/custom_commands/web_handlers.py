import discord
from aiohttp import web
import logging
import json
import io
from Main.database import add_to_history
from Main.utils import load_json
from .models import RequestItem, ReduxRequestItem, ReduxPromptRequestItem
from typing import Dict, Any
import asyncio
from .message_constants import STATUS_MESSAGES
from .views import ImageControlView, ReduxImageView, PuLIDImageView

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

        # Format the message content
        message_content = f"🎨 **Prompt:** {request_data['prompt']}\n"
        message_content += f"🎲 **Seed:** {request_data['seed']}\n"
        message_content += f"📐 **Resolution:** {request_data['resolution']}"
        
        if request_data.get('loras'):
            loras = json.loads(request_data['loras'])
            if loras:
                message_content += f"\n🔧 **LoRAs:** {', '.join(loras)}"

        # Get the original message to reply to
        try:
            original_message = await channel.fetch_message(int(request_data['original_message_id']))
            await original_message.reply(content=message_content, file=file)
        except (discord.NotFound, discord.HTTPException) as e:
            # If we can't find the original message or there's an error replying, send as new message
            await channel.send(content=message_content, file=file)

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