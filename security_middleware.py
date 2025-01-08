from typing import Optional, Set, Dict, List
import re
import time
import logging
import ipaddress
import json
import os
from datetime import datetime, timedelta
from aiohttp import web
from aiohttp.web import middleware
from dataclasses import dataclass, field

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

@dataclass
class SecurityConfig:
    """Configuration for security settings"""
    max_requests_per_minute: int = 10
    block_duration_minutes: int = 60
    allowed_methods: Set[str] = field(default_factory=lambda: {'POST'})
    allowed_paths: Set[str] = field(default_factory=lambda: {'/update_progress', '/send_image', '/image_generated'})
    blocked_user_agents: Set[str] = field(default_factory=set)

class SecurityMiddleware:
    def __init__(self, config: SecurityConfig = SecurityConfig()):
        self.config = config
        self.request_counts: Dict[str, List[float]] = {}
        self.blocked_ips: Dict[str, float] = {}
        self.suspicious_attempts: Dict[str, int] = {}
        self.trusted_ips = {'127.0.0.1', 'localhost', '::1'}
        
        # Create security directory if it doesn't exist
        self.security_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'security')
        os.makedirs(self.security_dir, exist_ok=True)
        
        # Set path for blocked IPs file
        self.permanent_blocks_file = os.path.join(self.security_dir, "BlockedSecurityIps.json")
        self.permanent_blocks: Dict[str, dict] = self.load_permanent_blocks()

    def load_permanent_blocks(self) -> Dict[str, dict]:
        """Load permanently blocked IPs from JSON file"""
        try:
            if os.path.exists(self.permanent_blocks_file):
                with open(self.permanent_blocks_file, 'r') as f:
                    return json.load(f)
            return {}
        except Exception as e:
            logger.error(f"Error loading permanent blocks: {e}")
            return {}

    def save_permanent_blocks(self):
        """Save permanently blocked IPs to JSON file"""
        try:
            logger.warning(f"Attempting to save blocks to: {self.permanent_blocks_file}")
            logger.warning(f"Current blocks to save: {self.permanent_blocks}")
            
            # Ensure directory exists
            os.makedirs(os.path.dirname(self.permanent_blocks_file), exist_ok=True)
            
            with open(self.permanent_blocks_file, 'w') as f:
                json.dump(self.permanent_blocks, f, indent=2)
            logger.warning("Successfully saved blocked IPs to file")
        except Exception as e:
            logger.error(f"Error saving permanent blocks: {str(e)}")
            logger.error(f"Current directory: {os.getcwd()}")
            logger.error(f"File path: {self.permanent_blocks_file}")
            logger.error(f"Directory exists? {os.path.exists(os.path.dirname(self.permanent_blocks_file))}")
            logger.error(f"Full exception: {repr(e)}")

    def add_permanent_block(self, ip: str, reason: str):
        """Add an IP to permanent block list"""
        if not self.is_trusted_ip(ip):
            logger.warning(f"Adding permanent block for IP {ip} with reason: {reason}")
            current_time = datetime.now().isoformat()
            self.permanent_blocks[ip] = {
                'timestamp': current_time,
                'reason': reason
            }
            logger.info(f"Added block for {ip} at {current_time}")
            self.save_permanent_blocks()
            logger.warning(f"IP {ip} permanently blocked: {reason}")

    def is_trusted_ip(self, ip: str) -> bool:
        """Check if IP is in trusted list"""
        return ip in self.trusted_ips

    def is_bot_endpoint(self, request: web.Request) -> bool:
        """Check if the request is for a bot endpoint"""
        return request.path in self.config.allowed_paths and request.method == 'POST'

    def is_permanently_blocked(self, ip: str) -> bool:
        """Check if IP is permanently blocked"""
        return ip in self.permanent_blocks

    def is_ip_blocked(self, ip: str) -> bool:
        """Check if an IP is currently blocked"""
        if self.is_trusted_ip(ip):
            return False
        if self.is_permanently_blocked(ip):
            return True
        if ip in self.blocked_ips:
            block_time = self.blocked_ips[ip]
            if time.time() - block_time < self.config.block_duration_minutes * 60:
                return True
            else:
                del self.blocked_ips[ip]
                if ip in self.suspicious_attempts:
                    del self.suspicious_attempts[ip]
        return False

    def track_suspicious_attempt(self, ip: str) -> bool:
        """Track suspicious attempts and block IP if threshold exceeded"""
        if self.is_trusted_ip(ip):
            return False
        if ip not in self.suspicious_attempts:
            self.suspicious_attempts[ip] = 1
        else:
            self.suspicious_attempts[ip] += 1
            
        if self.suspicious_attempts[ip] >= 3:
            self.add_permanent_block(ip, "Multiple suspicious attempts")
            return True
        return False

    def is_rate_limited(self, ip: str) -> bool:
        """Check if an IP has exceeded the rate limit"""
        if self.is_trusted_ip(ip):
            return False
        current_time = time.time()
        if ip not in self.request_counts:
            self.request_counts[ip] = []
        
        self.request_counts[ip] = [t for t in self.request_counts[ip] 
                                 if current_time - t < 60]
        
        if len(self.request_counts[ip]) >= self.config.max_requests_per_minute:
            self.add_permanent_block(ip, "Rate limit exceeded")
            return True
            
        self.request_counts[ip].append(current_time)
        return False

    def is_suspicious_request(self, request: web.Request) -> bool:
        """Check if a request appears suspicious"""
        if self.is_trusted_ip(request.remote) and self.is_bot_endpoint(request):
            return False

        # Immediately block unauthorized paths
        if request.path not in self.config.allowed_paths:
            self.add_permanent_block(
                request.remote, 
                f"Unauthorized path access: {request.path}"
            )
            return True

        if request.method not in self.config.allowed_methods:
            return True

        user_agent = request.headers.get('User-Agent', '')
        if user_agent in self.config.blocked_user_agents:
            return True

        return False

    @middleware
    async def middleware(self, request: web.Request, handler) -> web.Response:
        """Main middleware handler"""
        client_ip = request.headers.get('X-Forwarded-For', request.remote)
        logger.info(f"Processing request from IP: {client_ip}, Path: {request.path}")

        # Check if IP is permanently blocked
        if client_ip in self.permanent_blocks:
            logger.warning(f"Blocked request from permanently blocked IP: {client_ip}")
            return web.Response(
                status=403,
                text="Access Denied: Your IP address has been permanently blocked due to suspicious activity.",
                content_type='text/plain'
            )

        # Check if path is allowed
        if request.path not in self.config.allowed_paths:
            logger.warning(f"Unauthorized path access attempt from {client_ip}: {request.path}")
            self.add_permanent_block(client_ip, f"Unauthorized path access: {request.path}")
            return web.Response(
                status=403,
                text="Access Denied: This API endpoint is not accessible. Repeated unauthorized attempts will result in a permanent block.",
                content_type='text/plain'
            )

        # Check HTTP method
        if request.method not in self.config.allowed_methods:
            logger.warning(f"Invalid method {request.method} from {client_ip}")
            self.add_permanent_block(client_ip, f"Invalid method: {request.method}")
            return web.Response(
                status=405,
                text="Method Not Allowed: This request method is not supported. Repeated invalid attempts will result in a permanent block.",
                content_type='text/plain'
            )

        # Check rate limiting
        current_time = time.time()
        if not self.is_trusted_ip(client_ip):
            if client_ip not in self.request_counts:
                self.request_counts[client_ip] = []
            
            # Clean old requests
            self.request_counts[client_ip] = [t for t in self.request_counts[client_ip] 
                                            if current_time - t < 60]
            
            # Check rate limit
            if len(self.request_counts[client_ip]) >= self.config.max_requests_per_minute:
                logger.warning(f"Rate limit exceeded for IP: {client_ip}")
                self.add_permanent_block(client_ip, "Rate limit exceeded")
                return web.Response(
                    status=429,
                    text="Too Many Requests: Rate limit exceeded. Your IP has been blocked due to excessive requests.",
                    content_type='text/plain'
                )
            
            # Add current request
            self.request_counts[client_ip].append(current_time)

        try:
            response = await handler(request)
            return response
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            return web.Response(
                status=500,
                text="Internal Server Error: The request could not be processed.",
                content_type='text/plain'
            )

def setup_security_middleware(app: web.Application, config: Optional[SecurityConfig] = None) -> None:
    """Setup security middleware with optional custom configuration"""
    security = SecurityMiddleware(config or SecurityConfig())
    app.middlewares.append(security.middleware)
