from aiohttp import web
from security_middleware import setup_security_middleware
from app_config import SECURITY_CONFIG

async def init_app() -> web.Application:
    app = web.Application()
    
    # Setup security middleware with custom configuration
    setup_security_middleware(app, SECURITY_CONFIG)
    
    # Add your existing routes and configuration here
    
    return app

if __name__ == '__main__':
    app = init_app()
    web.run_app(app, host='0.0.0.0', port=8080)
