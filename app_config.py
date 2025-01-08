from security_middleware import SecurityConfig

# Custom security configuration
SECURITY_CONFIG = SecurityConfig(
    max_requests_per_minute=60,
    block_duration_minutes=30,
    allowed_methods={'POST'},  # Only allow POST method
    allowed_paths={
        '/update_progress',
        '/send_image',
        '/image_generated'
    },
    blocked_user_agents={
        'Go-http-client/1.1',
        'fasthttp',
        'curl/7.68.0',
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/70.0.3538.77 Safari/537.36'
    }
)
