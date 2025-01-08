import aiohttp
import asyncio
import logging
import json
import os
from datetime import datetime

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Set up paths
SECURITY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'security')
BLOCKED_IPS_FILE = os.path.join(SECURITY_DIR, "BlockedSecurityIps.json")

def check_blocked_ips_file():
    """Check the contents of the blocked IPs file"""
    if os.path.exists(BLOCKED_IPS_FILE):
        try:
            with open(BLOCKED_IPS_FILE, 'r') as f:
                blocked_ips = json.load(f)
                logger.info(f"\nBlocked IPs file contents from: {BLOCKED_IPS_FILE}")
                for ip, data in blocked_ips.items():
                    logger.info(f"IP: {ip}")
                    logger.info(f"Timestamp: {data['timestamp']}")
                    logger.info(f"Reason: {data['reason']}")
                    logger.info("-" * 50)
        except Exception as e:
            logger.error(f"Error reading blocked IPs file: {e}")
    else:
        logger.warning(f"Blocked IPs file does not exist yet at: {BLOCKED_IPS_FILE}")

async def test_security():
    async with aiohttp.ClientSession() as session:
        base_url = "http://localhost:8080"
        
        # Test 1: Access unauthorized endpoint
        logger.info("\nTest 1: Testing unauthorized endpoint access...")
        headers = {'User-Agent': 'SecurityTest/1.0'}
        paths_to_test = ['/admin', '/wp-login.php', '/phpmyadmin', '/api/unauthorized']
        
        for path in paths_to_test:
            async with session.get(f"{base_url}{path}", headers=headers) as response:
                body = await response.text()
                logger.info(f"Accessing {path}: Status {response.status}")
                logger.info(f"Response: {body}")
                # Check if file was created after each request
                check_blocked_ips_file()
                await asyncio.sleep(1)  # Small delay between requests

        # Test 2: Verify IP is blocked for legitimate endpoints
        logger.info("\nTest 2: Verifying IP is blocked for legitimate endpoints...")
        async with session.post(f"{base_url}/update_progress", headers=headers) as response:
            body = await response.text()
            logger.info(f"Accessing /update_progress after block: Status {response.status}")
            logger.info(f"Response: {body}")

        # Test 3: Test with different IP
        logger.info("\nTest 3: Testing with different IP...")
        headers = {
            'User-Agent': 'SecurityTest/1.0',
            'X-Forwarded-For': '192.168.1.2'
        }
        
        async with session.get(f"{base_url}/another-bad-path", headers=headers) as response:
            body = await response.text()
            logger.info(f"New IP accessing bad path: Status {response.status}")
            logger.info(f"Response: {body}")
            check_blocked_ips_file()

        # Test 4: Rate limiting leading to permanent block
        logger.info("\nTest 4: Testing rate limiting with another IP...")
        headers = {
            'User-Agent': 'SecurityTest/1.0',
            'X-Forwarded-For': '192.168.1.3'
        }
        
        for i in range(15):  # More than max_requests_per_minute
            async with session.post(f"{base_url}/update_progress", headers=headers) as response:
                if i % 5 == 0 or response.status != response.status:
                    body = await response.text()
                    logger.info(f"Request {i}: Status {response.status}")
                    logger.info(f"Response: {body}")
                await asyncio.sleep(0.1)
        
        # Final check of blocked IPs file
        logger.info("\nFinal check of blocked IPs file:")
        check_blocked_ips_file()

async def main():
    logger.info("Starting security middleware tests...")
    
    # Create security directory if it doesn't exist
    os.makedirs(SECURITY_DIR, exist_ok=True)
    
    # Display current blocked IPs if file exists
    if os.path.exists(BLOCKED_IPS_FILE):
        logger.info("Current blocked IPs before test:")
        check_blocked_ips_file()
    
    await test_security()
    logger.info("Security tests completed!")

if __name__ == "__main__":
    asyncio.run(main())
