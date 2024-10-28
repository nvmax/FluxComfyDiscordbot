from aiohttp import web
from Main.custom_commands.web_handlers import handle_generated_image, update_progress
import logging
from config import server_address

logger = logging.getLogger(__name__)

async def start_web_server(bot):
    app = web.Application()
    app['bot'] = bot
    app.router.add_post('/send_image', handle_generated_image)
    app.router.add_post('/update_progress', update_progress)
    
    runner = web.AppRunner(app)
    await runner.setup()
    # Changed to bind to 0.0.0.0 instead of specific IP
    site = web.TCPSite(runner, host="0.0.0.0", port=8080)
    await site.start()
    logger.info(f"Web server started on 0.0.0.0:8080 (ComfyUI server: {server_address})")

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

async def update_progress_message(bot, request_item, progress_data):
    try:
        channel = await bot.fetch_channel(int(request_item.channel_id))
        message = await channel.fetch_message(int(request_item.original_message_id))
        
        if isinstance(progress_data, dict):
            status = progress_data.get('status', '')
            msg = progress_data.get('message', 'Processing...')
            progress = progress_data.get('progress', 0)
        else:
            status = 'generating'
            progress = int(progress_data)
            msg = f'Generating image... {progress}% complete'

        if progress % 10 == 0 or status != 'generating':
            await message.edit(content=msg)
            logger.debug(f"Updated progress message: {msg}")
            
    except Exception as e:
        logger.error(f"Error updating progress message: {str(e)}")