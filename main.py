from aiohttp import web

async def init_app() -> web.Application:
    app = web.Application()
    
    # Add your existing routes and configuration here
    
    return app

if __name__ == '__main__':
    app = init_app()
    web.run_app(app, host='0.0.0.0', port=8080)