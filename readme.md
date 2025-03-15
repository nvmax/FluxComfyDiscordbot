# ComfyUI Discord Flux Bot 🤖✨

<p align="center">
  <img src="Comfyuidiscordbotflux.png" alt="ComfyUI Discord Bot" width="600">
</p>

<div align="center">

[![Discord](https://img.shields.io/badge/Discord-Join%20Community-7289DA?style=for-the-badge&logo=discord&logoColor=blue)](https://discord.gg/V3pRgtzjsN)
[![GitHub Stars](https://img.shields.io/github/stars/nvmax/FluxComfyDiscordbot?style=for-the-badge)](https://github.com/nvmax/FluxComfyDiscordbot/stargazers)
[![License](https://img.shields.io/badge/License-MIT%20Dual-green.svg?style=for-the-badge)](docs/LICENSE.md)

</div>

## 🌟 Overview
Welcome to the world of AI-powered imagination with Comfyui Discord Flux Bot! This fantastic bot is your gateway to transforming text into stunning visuals, bringing your wildest ideas to life with just a few keystrokes, and share with your friends in discord.

Whether you're an artist looking for inspiration, a writer wanting to visualize your scenes, or just someone who loves to explore the boundaries of creativity, this bot is your perfect companion. It's designed to make the process of AI image generation accessible, fun, and endlessly fascinating, and shareable with your friends in discord.

Transform your Discord server into an AI art studio! bring the power of AI-generated imagery directly to your Discord community. With just a few simple commands, users can create stunning visuals from text descriptions, experiment with different styles, and share their creations instantly.

### ✨ Key Features

- 🎨 **Text-to-Image Generation**: Convert your ideas into beautiful images
- 🔧 **Multiple Resolution Options**: Choose the perfect size for your creations
- 🎨 **Creativity**: Adjust the creativity level for unique results using LMStudio or other AI LLM's
- 🎭 **LoRA Support**: Apply various styles and characteristics to your generations
- 🔍 **Upscaling Capabilities**: Enhance image quality with advanced upscaling
- 💬 **Discord Integration**: Seamless sharing and community interaction

## 📚 Documentation

- [🚀 Quick Start Guide](docs/quick-start.md)
- [📖 Complete Installation Guide](docs/installation.md)
- [⚙️ Configuration](docs/configuration.md)
- [📝 Usage & Commands](docs/commands.md)
- [🔄 Latest Updates](docs/changelog.md)
- [❓ Troubleshooting](docs/troubleshooting.md)

## 🚀 Quick Start

1. **Prerequisites**
   - ComfyUI installation
   - Discord Bot Token
   - Python 3.10+

2. **Basic Setup**
   ```bash
   # Clone the repository
   git clone https://github.com/yourusername/comfyui-discord-bot
   
   # Run the setup tool
   python setup.py
   ```

3. **Configure**
   - Set up your Discord bot token
   - Configure your ComfyUI path
   - Start generating!

[➡️ Full Installation Guide](docs/installation.md)

## 🆕 Latest Updates
### March 3, 2025
- **Video Wan2.1 **
  - Now supports T2V thanks to wan2.1 checkpoints
  - Creates 5 sec clips using text to video.
  - Now supporting Teacache for video generations increasing speed of video generations.
  - Command in discord /video
  - As features come available and new loras, I will introduce them to the video option.
  - Image2video is coming, working on it. 
    - Various other fixes 
      - Refactored some code to resolve small bugs, updated setup tool to better support downloads with out time outs, progress bar now shows for every file being downloaded
      resolved issues with lora editor not having options to make loras active or inactive, button now down at the bottom of tool.
      - Updated setup instructions to support wan2.1 options

- Side note, security middleware removed, comfyiu has implemented it on their side no longer needed if you are running the latest version of comfyui.

### January 17, 2025
- **PuLID Workflow**
  - Now supports PuLID workflow
  - Upload a reference image to generate an image using a PuLID just fill in style information
    - example: image of a woman wearing a yellow dress,  "/pulid select your resolution, enter in the prompt " woman with a red dress"

### January 10, 2025
- **Security Implementation**
  - Implemented a security middleware to prevent abuse and protect against malicious requests.
  - Added a permanent block list to block IP addresses that have been repeatedly tried to access restricted endpoints.
  - you can check the security folder for the permanent block list and see what they were requesting.
- **AI Prompt Enhancements**
  - Now supports Google Gemini 2.0 Flash

### November 29, 2024
- **LMStudio / Ai Prompt Enhancements**
  - Now you can select LMStudio, xAI or OpenAI with in the setup tool
  - When generating prompts a modal will appear to select Creativity level
  - Creativity level can be adjusted from 1-10 with 1 not changing your prompt and 10 extremely creative.
  - can enable or disable AI Prompt Enhancements using the setup tool

- **Various fixes and improvements**
  - Added features to the setup tool for AI Prompt Enhancements
  - updated workflows in Datasets to support new clip models
  - updated Lora Editor and made it more user friendly and robust

[📝 View Full Changelog](docs/changelog.md)

## 🤝 Contributing

We welcome contributions! Check out our [Contributing Guidelines](docs/CONTRIBUTING.md) to get started.

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](docs/LICENSE.md) file for details.

## 💖 Support

If you find this bot helpful, please consider:
- ⭐ Starring the repository
- 🤝 Contributing to the project
- 📢 Sharing with your community

---
<p align="center">Made with ❤️ by the ComfyUI Discord Bot Team</p>
