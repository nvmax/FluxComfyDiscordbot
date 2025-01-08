from aiohttp import web
from Main.custom_commands.web_handlers import handle_generated_image
import logging
from Main.custom_commands.message_constants import STATUS_MESSAGES
from config import server_address
import discord
from security_middleware import SecurityMiddleware
from app_config import SecurityConfig

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

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
        
        try:
            channel = await request.app['bot'].fetch_channel(int(request_item.channel_id))
            message = await channel.fetch_message(int(request_item.original_message_id))
            
            status = progress_data.get('status', '')
            progress_message = progress_data.get('message', 'Processing...')
            progress = progress_data.get('progress', 0)

            status_info = STATUS_MESSAGES.get(status, {
                'message': progress_message,
                'emoji': '⚙️'
            })

            if status == 'generating':
                formatted_message = f"{status_info['emoji']} {status_info['message']} {progress}%"
            elif status == 'error':
                formatted_message = f"{status_info['emoji']} {status_info['message']} {progress_message}"
                # Only remove on error
                if request_id in request.app['bot'].pending_requests:
                    del request.app['bot'].pending_requests[request_id]
            else:
                formatted_message = f"{status_info['emoji']} {status_info['message']}"
            await message.edit(content=formatted_message)
            logger.debug(f"Updated progress message: {formatted_message}")
            return web.Response(text="Progress updated")
            
        except discord.errors.NotFound:
            logger.warning(f"Message {request_item.original_message_id} not found")
            return web.Response(text="Message not found", status=404)
        except discord.errors.Forbidden:
            logger.warning("Bot lacks permission to edit message")
            return web.Response(text="Permission denied", status=403)
        except Exception as e:
            logger.error(f"Error updating progress message: {str(e)}")
            return web.Response(text=f"Error: {str(e)}", status=500)
            
    except Exception as e:
        logger.error(f"Error in update_progress: {str(e)}")
        return web.Response(text="Internal server error", status=500)

async def start_web_server(bot):
    app = web.Application()
    
    # Configure security
    security_config = SecurityConfig()
    security_config.allowed_paths = {'/update_progress', '/send_image', '/image_generated'}  # Add other allowed paths as needed
    security_config.allowed_methods = {'POST'}
    security_config.max_requests_per_minute = 10
    
    # Add security middleware
    security = SecurityMiddleware(security_config)
    app.middlewares.append(security.middleware)
    
    # Setup routes
    app.router.add_post('/send_image', handle_generated_image)
    app.router.add_post('/update_progress', update_progress)
    app.router.add_post('/image_generated', handle_generated_image)
    
    app['bot'] = bot
    
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, host="0.0.0.0", port=8080)
    await site.start()
    logger.info(f"Web server started on 0.0.0.0:8080 (ComfyUI server: {server_address})")
    return app