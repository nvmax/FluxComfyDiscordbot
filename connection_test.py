import requests
import os
from dotenv import load_dotenv
import websocket
import time


def test_comfyui_connection(server):
    print(f"\nTesting ComfyUI connection to {server}:8188...")
    try:
        response = requests.get(f"http://{server}:8188/")
        print("✓ ComfyUI API is accessible")
        
        # Test WebSocket connection
        ws_url = f"ws://{server}:8188/ws"
        ws = websocket.create_connection(ws_url, timeout=10)
        ws.close()
        print("✓ ComfyUI WebSocket is accessible")
        return True
    except Exception as e:
        print(f"✗ Failed to connect to ComfyUI: {str(e)}")
        return False

def test_bot_webserver(server):
    print(f"\nTesting Bot Web Server connection to {server}:8080...")
    try:
        # Send a test request
        response = requests.post(
            f"http://{server}:8080/update_progress",
            json={"test": "connection"},
            timeout=5
        )
        print("✓ Bot Web Server is accessible")
        return True
    except Exception as e:
        print(f"✗ Failed to connect to Bot Web Server: {str(e)}")
        return False

def main():
    load_dotenv()
    
    bot_server = os.getenv('BOT_SERVER', 'localhost')
    comfy_server = os.getenv('server_address', 'localhost')
    
    print("Connection Test Utility")
    print("======================")
    
    comfy_ok = test_comfyui_connection(comfy_server)
    bot_ok = test_bot_webserver(bot_server)
    
    print("\nSummary")
    print("=======")
    print(f"ComfyUI Connection: {'✓ OK' if comfy_ok else '✗ Failed'}")
    print(f"Bot Web Server: {'✓ OK' if bot_ok else '✗ Failed'}")
    
    if not (comfy_ok and bot_ok):
        print("\nTroubleshooting Tips:")
        print("1. Check if the server addresses in .env are correct")
        print("2. Ensure both servers are running")
        print("3. Check if firewalls are allowing connections")
        print("4. Verify the ports (8188 for ComfyUI, 8080 for Bot) are not in use")
        print("5. Try running both servers with administrator privileges")

if __name__ == "__main__":
    main()