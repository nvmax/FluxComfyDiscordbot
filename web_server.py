from aiohttp import web
from Main.custom_commands.web_handlers import handle_generated_image
import logging

logger = logging.getLogger(__name__)

async def start_web_server(bot):
    app = web.Application()
    app['bot'] = bot
    app.router.add_post('/send_image', handle_generated_image)
    app.router.add_post('/update_progress', update_progress)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, 'localhost', 8080)
    await site.start()

async def update_progress(request):
    data = await request.json()
    request_id = data['request_id']
    progress = data['progress']
    if request_id in request.app['bot'].pending_requests:
        request_item = request.app['bot'].pending_requests[request_id]
        await update_progress_message(request.app['bot'], request_item, progress)
    return web.Response(text="Progress updated")

async def update_progress_message(bot, request_item, progress):
    try:
        channel = await bot.fetch_channel(int(request_item.channel_id))
        message = await channel.fetch_message(int(request_item.original_message_id))
        
        if progress % 10 == 0:
            await message.edit(content=f"Generating image... {progress}% complete")
    except Exception as e:
        logger.error(f"Error updating progress message: {str(e)}")