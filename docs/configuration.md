# ⚙️ Configuration Guide

## 🐳 Docker Installation

### Prerequisites
- Complete the standard installation and setup first
- Configure your LoRAs using the Lora_editor tool
- Docker and Docker desktop installed on your system


### 🤖 Discord Bot Setup

#### 1️⃣ Creating Your Discord Application
1. Visit the [Discord Developer Portal](https://discord.com/developers/applications)
2. Create New Application:
   - Click "New Application"
   - Name your bot
   - Navigate to "Bot" tab
   - Click "Add Bot"

#### 2️⃣ Bot Configuration
1. **Essential Bot Settings**
   - Copy Bot Token (keep secure!)
   - Enable Required Intents:
     ✓ Presence Intent
     ✓ Server Members Intent
     ✓ Message Content Intent

2. **Bot Permissions Setup**
   - Go to "OAuth2" tab
   - Select "bot" under Scopes
   - Required Permissions:
     ```
     ✓ Send Messages
     ✓ Manage Messages
     ✓ Embed Links
     ✓ Attach Files
     ✓ Read Message History
     ✓ Use Slash Commands
     ```
3. **Server Integration**
   - Copy OAuth2 URL
   - Open in new tab
   - Select target server

### 🛠️ Bot Configuration

#### Initial Setup
1. Create `.env` file in root directory:
   ```env
   COMMAND_PREFIX=/
   ```

2. Run Setup Tool:
   ```bash
   python setup.py
   # or use Setup.exe
   ```

<div align="center">
  <img src="../setuptool.jpg" width="500" alt="Setup Tool Interface">
  <img src="../setuptool2.jpg" width="500" alt="Setup Tool Interface">
</div>

#### 📝 Configuration Details

1. **Path Configuration**
   - Browse to ComfyUI models folder
   - Example: `C:/Comfyui_windows_portable/ComfyUI/models`

2. **API Tokens**
   - **Civitai Token:**
     1. Create account on [Civitai](https://civitai.com)
     2. Profile → Settings → Add API Key
   
   - **Huggingface Token:**
     1. Create account on [Huggingface](https://huggingface.co)
     2. Profile → Access Tokens
     3. Create token with "read access to public gated repos"

3. **Server Configuration**
   - Bot Server Address: Usually `127.0.0.1` (try `0.0.0.0` or `localhost` if needed)
   - ComfyUI Server: Same as bot (use remote IP if on different machine)

4. **Discord Settings**
   - Server IDs: Right-click server → Copy ID
   - Channel IDs: Right-click channel → Copy ID
   - Multiple IDs: Use comma separation (e.g., `123456789,987654321`)
   - Bot Manager Role ID (optional): For bot administration

5. **Model Selection**
   - Choose checkpoint based on GPU VRAM:
     - Support for 6GB to 24GB cards
     - Select version matching your VRAM capacity

### 🔧 Advanced Setup

#### Creating Executables
If you prefer building your own executables:
```bash
# Install PyInstaller
pip install pyinstaller

# Build Setup Tool
pyinstaller setup.spec --clean --noconfirm

# Build LoRA Editor
pyinstaller LoraEditor.spec --clean --noconfirm
```

#### ⚠️ Important Notes
- Required files will be automatically moved to their respective folders
- Checkpoint changes: Simply rerun setup tool
- Model changes require bot restart
- Antivirus may flag executables
  - Build your own using provided specs
  - OS-dependent compilation

### Docker Setup Steps

1. Initial Build and Start
   ```bash
   docker-compose up --build
   ```

2. Subsequent Starts
   After the initial build, you can start the container with:
   ```bash
   docker-compose up
   ```

### Troubleshooting Connection
If the bot doesn't connect to your ComfyUI instance, you may need to adjust the server address in the Dockerfile:

1. Locate Line 33 in the Dockerfile:
   ```dockerfile
   ENV server_address=0.0.0.0
   ```

2. Try one of these alternatives:
   - Local connection: `127.0.0.1`
   - Your network IP: `LOCAL NETWORK IP ADDRESS`
   - ComfyUI host IP (if running on different machine)

## 🎨 LoRA Models Configuration

### 🌟 Introduction to LoRA Models
LoRA (Low-Rank Adaptation) models are the secret sauce that brings magic to your image generations! These models can:
- Enhance image quality
- Apply specific artistic styles
- Add unique characteristics to generations
- Transform your prompts into stunning visuals

### 📥 Getting LoRA Models
1. Visit [Civitai.com/models](https://civitai.com/models)
2. Apply filters:
   - Model Type: `LoRA`
   - Base Model: `Flux.1s` and `Flux.1 D`
3. Download your chosen models
4. Place files in: `comfyui/models/Lora` folder

### 🛠️ LoRA Editor Tool

```bash
python lora_editor.py
# or build your own exe using the .spec file and pyinstaller
```

<div align="center">
  <img src="../loraeditor.png" width="600" alt="LoRA Editor Interface">
</div>

#### ✨ Latest Updates
- 🔗 URL links support for `/lorainfo` command
- 🚀 Support for 600+ LoRAs
- 💾 SQLite3 database for persistent storage
- 🎯 Persistent trigger words
- 🤗 Huggingface support
- 🤗  Civitai support
- 🔄 Reset All Loras 
- ⚡ Instant LoRA availability
- 📋 Lora arrangement abilities

#### 🚀 Getting Started
1. Launch the editor:
   ```bash
   python lora_editor.py
   # or build your own exe using the .spec file and pyinstaller
   ```


#### 🎯 Key Features
- 🔄 Auto-download LoRAs from URLs
- 🎯 Automatic trigger word population
- ⚖️ Pre-configured weights (default: 1.0)
    -if lora weight is less than 1, keep it do not change
- 📊 Easy weight customization
- 📋 Flexible list organization
- 🔗 Activate and deactivate loras 


### 📝 Manual Configuration
If you prefer manual setup, edit `datasets/lora.json`:

```json
{
  "name": "Your LoRA Name",
  "add_prompt": "required_trigger_word",
  "file": "MyLoRA.safetensors",
  "weight": 1.0,
  "url": "https://civitai.com/api/download/models/123456789/MyLoRA.safetensors"
}
```

### 💡 Best Practices
1. **Weight Management**
   - Default: 1.0
   - Adjust lower for subtle effects
   - Test different values for optimal results

2. **Organization**
   - Use descriptive names
   - Editing the trigger words may result in loras not working
   - URL is auto populated.


### 🔍 Troubleshooting
- Verify file extensions (.safetensors)
- Confirm trigger words
- Test API connectivity

## 🔧 Bot Configuration

### Environment Variables
All environment variables are auto created when setup is ran

### Server Configuration
1. Enable `--listen` on ComfyUI server
2. Configure port settings (default: 8188)
3. Set up SSL if needed (recommended for production)