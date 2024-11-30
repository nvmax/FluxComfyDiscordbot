# ❓ Troubleshooting Guide

## 🔍 Common Issues and Solutions

## Troubleshooting 
Encountering issues? Don't worry! Here are some common problems and simple solutions to get you back to creating amazing images. 

### Recommended Hardware Requirements for the best experience, I recommend:
 -  CPU: Recent Intel or AMD processor 
 -  RAM: 64GB of system memory 
 -  GPU: NVIDIA RTX 3090 or 4090 
 - While lower specifications may work, you might experience slower performance or limitations in image size and quality. If you have lower-end hardware: - You may need to adjust settings in ComfyUI to work with lower memory GPUs. - Check the [ComfyUI documentation](https://github.com/comfyanonymous/ComfyUI) for optimizations for lower-end hardware. 

 ### Supports lower Vram GPUS thanks to FluxFusion.
   - Min recommended specs:
    - Cpu: Intel Xeon E5 or i5 or Ryzen 5 or higher
    - Ram: 32GB (for bot and comfyui)
    - Gpu: RTX 3060 Ti or equivalent.

### Common Issues 
1.  **Bot Not Responding** - Ensure the bot is online and has proper permissions in your Discord server. - Check if you're using the command in an allowed channel. 
2.  **Slow Image Generation** - This could be due to high server load or limited hardware resources. - Be patient, or try again at a less busy time, Bot does use a queue system to keep track of all requests.
3.  **Error Messages** - If you see specific error messages, try restarting the bot. - Check the bot's console output for more detailed error information, you may also join discord and ask for help.
4.  **Installation Problems** - Ensure you have Python 3.x installed correctly. - Verify that all dependencies are installed using `pip install -r requirements.txt`. 
5.  **GPU Not Detected** - Make sure you have the latest NVIDIA drivers installed. - Confirm that your GPU is CUDA-compatible and properly recognized by your system. 
6.  **Out of Memory Errors** - Try generating smaller images or using fewer LoRAs. - Close other resource-intensive applications on your system. 

### Still Having Trouble? If you're still experiencing issues: 
- Double-check all configuration settings by running the Setup.py or setup.exe.  
- Consult the ComfyUI documentation for advanced troubleshooting specific to the image generation backend.
		- There are options to use lowvram for comfyui this may allow it to work on 4070's 4060's and AMD GPUs with less that 24GB of VRam, even if you are running fluxfusion checkpoints. 

### 🚫 Bot Won't Start

#### Symptoms
- Bot fails to launch
- Error messages during startup
- No response from bot

#### Solutions
1. **verify discord bot is setup correctly**
   - Check if the bot is online and has proper permissions in your Discord server
   - Check if you're using the command in an allowed channel
   - double check instructions in installation guide [📖 Complete Installation Guide](docs/installation.md)
2. **Check Python Version**
   ```bash
   python --version
   ```
   - Ensure Python 3.10+ is installed
   - Verify it's in your system PATH

3. **Verify Dependencies**
   ```bash
   pip install -r requirements.txt
   ```
   - Check for any error messages
   - Try updating pip: `python -m pip install --upgrade pip`

4. **Configuration Issues**
   - Verify `config.json` exists
   - Check bot token is correct
   - Confirm ComfyUI path is valid

### 🖼️ Image Generation Problems

#### Symptoms
- Images fail to generate
- Low-quality outputs
- Generation takes too long

#### Solutions
1. **ComfyUI Connection**
   - Verify ComfyUI is running
   - Check workflow file exists
   - Confirm port settings

2. **LoRA Issues**
   - Verify LoRA files exist
   - Check file permissions
   - Confirm LoRA paths in config

3. **Performance Issues**
   - Monitor GPU usage
   - Check available memory
   

### 🔌 Discord Connection Issues

#### Symptoms
- Bot shows offline
- Commands not responding
- Permissions errors
- double check instructions in installation guide [📖 Complete Installation Guide](docs/installation.md)

#### Solutions
1. **Token Verification**
   - Regenerate bot token
   - Update token in config
   - Check bot permissions

2. **Discord API**
   - Verify bot intents are enabled
   - Check Discord API status
   - Confirm server permissions

### ⚠️ Numpy 2 Compatibility

- bot will patch numpy to allow it to run nodes with numpy 2. 
- If you're running into issues with numpy 2 please report them [here](https://github.com/nvmax/FluxComfyDiscordbot/issues).

## 🆘 Getting Help

If you're still experiencing issues:

1. **Check Logs**
   - Review bot logs
   - Check ComfyUI logs
   - Look for error messages

2. **Community Support**
   - Join our [Discord Server](https://discord.gg/your-invite-link)
   - Check [GitHub Issues](https://github.com/yourusername/comfyui-discord-bot/issues)
   - Search existing solutions

3. **Report a Bug**
   - Provide detailed description
   - Include error messages
   - Share system information
      -cpu, gpu, ram, os, python version, etc.

## 🆘 Still Need Help?


- Join our [Discord Server](https://discord.gg/V3pRgtzjsN)
- Open an [Issue](https://github.com/nvmax/FluxComfyDiscordbot/issues)