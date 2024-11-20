import os
import requests
import zipfile
from pathlib import Path
import sys

def download_upx():
    # UPX version to download
    UPX_VERSION = "4.1.0"
    
    # Determine system architecture
    is_64bits = sys.maxsize > 2**32
    
    # Construct filename based on system
    if sys.platform == "win32":
        arch = "win64" if is_64bits else "win32"
        filename = f"upx-{UPX_VERSION}-{arch}.zip"
    else:
        raise RuntimeError("Unsupported platform")

    # URLs
    base_url = f"https://github.com/upx/upx/releases/download/v{UPX_VERSION}/"
    url = base_url + filename

    # Local paths
    script_dir = Path(__file__).parent
    upx_dir = script_dir / "upx"
    upx_dir.mkdir(exist_ok=True)

    # Download and extract
    print(f"Downloading UPX {UPX_VERSION}...")
    response = requests.get(url)
    response.raise_for_status()

    zip_path = upx_dir / filename
    with open(zip_path, 'wb') as f:
        f.write(response.content)

    print("Extracting UPX...")
    with zipfile.ZipFile(zip_path, 'r') as zip_ref:
        zip_ref.extractall(upx_dir)

    # Clean up
    zip_path.unlink()
    
    # Return the path to the upx executable
    upx_exe_dir = upx_dir / f"upx-{UPX_VERSION}-{arch}"
    return str(upx_exe_dir)

if __name__ == "__main__":
    download_upx()
