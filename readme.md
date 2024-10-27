

<p align="center">
  <img src="Comfyuidiscordbotflux.png" alt="Alt text" class="responsive-image">
</p>

Welcome to the world of AI-powered imagination with My Comfyui Discord Bot! This fantastic bot is your gateway to transforming text into stunning visuals, bringing your wildest ideas to life with just a few keystrokes, and share with your friends in discord.  

Imagine a digital artist that never sleeps, always ready to paint your dreams and fantasies. That's exactly what this bot offers! With the power of advanced AI, it can generate images from your text prompts, allowing you to explore visual concepts you might never have thought possible.

But it doesn't stop at simple text-to-image conversion. This bot comes equipped with a variety of options to fine-tune your creations:  

- Choose from different resolutions to get the perfect size for your needs.

- Apply LoRA (Low-Rank Adaptation) models to infuse specific styles or characteristics into your images.

- Adjust upscaling factors to increase resolution for larger image generations. 

  

Whether you're an artist looking for inspiration, a writer wanting to visualize your scenes, or just someone who loves to explore the boundaries of creativity, this bot is your perfect companion. It's designed to make the process of AI image generation accessible, fun, and endlessly fascinating, and shareable with your friends in discord.

  

So, are you ready to dive into a world where your words paint pictures? Where your imagination knows no bounds? Where you can create images you never even knew you could think of? Then you're in the right place! Let's embark on this exciting journey of AI-powered creativity together!

## Table of Contents
1. [Prerequisite](#prerequisite)
2. [Installation](#installation)
3. [Setting up the Discord Bot](#setting-up-the-discord-bot)
4. [Configuring the Bot](#configuring-the-bot)
5. [Getting Started](#getting-started)
6. [Troubleshooting](#troubleshooting)
7. [Contributing](#contributing)
8. [License](#license)


    #### prerequisite 
    1. [Comfyui](https://github.com/comfyanonymous/ComfyUI) please install and configure for use.
    - Please enable --listen on your comfyui server. 
    2. Flux required files:
        *Flux.1 Dev and associated files in correct folders in comfyui please refer to [Comfyui Wiki Manual](https://comfyui-wiki.com/tutorial/advanced/flux1-comfyui-guide-workflow-and-examples) for this. 
        - Note: the bot will not work without these files.
        - File names are specific.
            * flux1-dev.sft
            * t5xxl_fp8_e4m3fn.safetensors
            * clip_l.safetensors
            * ae.sft
          - For faster generations look at using [Flux Fusion V2](https://civitai.com/models/630820/flux-fusion-v2-4-steps-gguf-nf4-fp8fp16) download the FP15 or FP8 version.
           - place in your comfyui/models/unet folder.
              - use fluxfusion.json for the FluxFusion V2 model.
    3. copy over the 4x-ClearRealityV1.pth into your comfyui/models/upscale_models folder.
    4. [Required Files](#requiredfiles)

## Installation

   

1. Clone the repository or download the source code to your local machine. 

2. Ensure you have Python 3.x installed on your system. You can download it from [python.org](https://www.python.org/downloads/). 

3. Open a terminal or command prompt and navigate to the directory containing the bot files. 

4. Install the required dependencies using the requirements.txt file: 
 ```pip install -r requirements.txt```

This command will install all the necessary libraries for the bot to function. 

5. Follow the configuration steps outlined in the [Setting up the Discord Bot](#Setting-up-the-Discord-Bot) section to set up your bot token and other settings.

6. Startup comfyui and load the workflow.json file.

7. Once everything is configured, you can run the bot using: 
``` Python bot.py```
 

The bot should now be running and connected to your Discord server. 

Note: If you close the terminal, you'll need to activate it again before running the bot.py

 


## Setting up the Discord Bot

  

1. Go to the [Discord Developer Portal](https://discord.com/developers/applications). 

 * Click on "New Application" and give your bot a name. 
 * Once created, go to the "Bot" tab in the left sidebar. 
 * Click "Add Bot" to create a bot user for your application.
 * Under the bot's username, you'll see a "Token" section. Click "Copy" to copy your bot token. Keep this token secret and secure.
 * In the "Privileged Gateway Intents" section, enable the following intents:
   * Presence Intent
   * Server Members Intent
   * Message Content Intent
* Go to the "OAuth2" tab in the left sidebar.
* In the "Scopes" section, select "bot".
* In the "Bot Permissions" section, select the permissions your bot needs. At minimum, it will need:- 
	* Read Messages/View Channels
	* Send Messages
	* Embed Links
	* Attach Files
	* Read Message History
	* Use Slash Commands

2. Copy the generated OAuth2 URL at the bottom of the "Scopes" section. 

3. Open a new browser tab, paste the URL, and select the server where you want to add the bot.

## Configuring the Bot
1. Create a new .env  file in a text editor, you can also use the provided example just rename to .env after you have 
configured it.
2. Replace the placeholder token with your actual bot token: ``` DISCORD_TOKEN = 'your_bot_token_here'```
3. Update the ```ALLOWED_SERVERS``` with the id of your server or servers, no quotes separate with a comma
4. Update the `CHANNEL_IDS` of the channel in discord you want it to respond in, multiple can be added no quotes separate with a comma
		-Note: This restricts it from being ran in any and all channels, if you dont specify a channel the bot can be used in any channel on the discord server " may make a mess " 
5. Set the `bot_manager_role_id` to the ID of the role that should have access to bot management commands.
	-Note: this is not ADMIN, this is used for managing the bot if you are not the admin of the server.
	  
      - Case: if your friend you trust wants to be able to ban specific users or words or even reboot the server this would give him the permissions to do so but not give him Admin privileges on your discord server.
	  
      - There is no Admin role since all intents are pulled from discord, Discord Admins already have the rights and intents for all options to admin the bot. 
6. Set the `server_address` to the address of your comfyui server. if its running on the same machine as the bot just use 127.0.0.1 if its on another machine please use the ip address of the machine running comfyui.
	  
#### LoRA (Low-Rank Adaptation) models Config

This is where the magic happens, LoRA models can enhance and apply a specific feeling or desired result to a image,  You can download various lora's from [Civitai.com/models](https://civitai.com/models) use the filter options and select LoRA under Model types, and select Flux.1s and Flux.1 D under Base model this will sort the models that you can use with this bot.

These models will go in your comfyui/models/Lora folder.

### adding LoRA's to your bot

1. open the lora.json file located in /Datasets 
    * Add name of your LoRA you downloaded or use a name you choose so you know what it is, this does not need to be the actual name of the file.
    * add_prompt :  if the lora requires a trigger word place it in this field
    * file: this is the exact name of the LoRA file with .safetensors, Example: MyLoRA.safetensors
    * weight:  this is the weight required to get the desired effect from the lora.  
	    * 0.5 is Ideal if you are wanting to use multiple LoRA's at one time, having many at 1.0 can cause mass hallucination on image generations.
      -- New tool: Lora_editor open from cmd window, select your comfyui/models/Lora folder, this will open a cmd window and allow you to select your lora and edit the weight.
	- Limitations 
		* 25 loras excluding default, in this list, this is hard coded by discord not of my choosing. 
    * currently there are examples in this file, please download and change these to reflect the correct loras that you have for flux. adding more than 25 will result in an error on discord and will not register bot commands.

#### Banned words or people

1. Located in /Datasets 
 * Here you can specify banned words that you do not wish to have people create images of or context of, any part of the word used will result in the person losing rights to generate images automatically.
 * Admin or Bot Manager can review, unban or even ask it why using the slash commands in discord
	 * /add_banned_word "word"
	 * /ban_user "discord id"
	 * /list_banned_users  - lists all that have been banned (should display the discord name)
	 * /list_banned_words - lists all banned words currently checking for
	 * /remove_banned_word - removes specified word
	 * /unban_user "discord id"
	 * /whybanned "discord id" - gives reason why this person was banned and the prompt they tried to use. 
     * /reboot - reboots the bot, this is useful if you are having issues with the bot and need to restart it.



<h3 id="requiredfiles" style="color: red; font-size: 24px;">REQUIRED FILES</h3>



Required Files folder, these are critical and needed to make sure the bot works right with the workflow and resolutions that flux can support.
1. workflow.json - after comfyui is installed load this lora, install all needed nodes using its manager. 
 - this is the workflow for comfyui to use for image generations, the bot uses the api format of this file.
2. ratios.json - this is a edit of mikey_nodes to add more resolutions that his nodes did not have that flux supports, location  ```ComfyUI_windows_portable\ComfyUI\custom_nodes\mikey_nodes```
  - replace exsisting ratios.json with one provided.
3. copy over the 4x-ClearRealityV1.pth into your comfyui/models/upscale_models folder.
4. if using FluxFusion V2 4 steps GGUF NF4 FP8FP16.safetensors please download and place in your comfyui/models/checkpoints folder.




## Getting Started 
1. First things first, make sure you're in a channel where the bot is active. Your server admin will know which channels these are! 
2. To summon our artistic AI companion, you'll use the `/comfy` command. It's like saying "Hey, AI, let's make some art!"

#### Creating Your Masterpiece 
1. Type `/comfy` in the chat, and you'll see a menu pop up. This is where the magic begins! 
2.  In the "prompt" field, describe the image you want to create. Be as creative and detailed as you like! For example: "A steampunk cat piloting a flying teapot over a city of clockwork buildings" 
3. Choose your desired "resolution" from the dropdown menu. This determines the size and shape of your image. 
4. (Optional) Want your image extra large? Set an "upscale_factor" between 1 and 4
		* Higher numbers make the image larger it is a factor of scale 1024x1024x2 = 2048x2048. 
5. (Optional) Feeling lucky? Add a "seed" number for consistent results. Or leave it blank for a surprise each time! 
6. Hit enter, and watch the magic unfold!

#### Customizing with LoRAs 
After you send the command, the bot will ask you to choose LoRAs (Low-Rank Adaptations). 
These are like special artistic styles or themes. Select the ones you want to apply to your image. It's like choosing different brushes for a painting! 

#### Waiting for Your Art
 The bot will start generating your image. It might take a little while - great art takes time, after all! You'll see progress updates, so you know it's hard at work.
			 - when it starts there maybe a long pause before it starts showing generation, this is loading the Flux models and loras selected. speed is dependent on the machine its running on

#### Admiring and Adjusting 
Once your image appears, you have a few options:
		 - 📚 "Options": Want to tweak your creation? This lets you adjust the resolution, LoRAs, or prompt and generate a new version. 
		 - ♻️ "Regenerate": Love the idea but want to see a different take? This creates a new image with the same settings. 
		 - 🗑️ "Delete": Not quite what you were looking for? You can remove the image.

#### Tips for Great Results 
- Be specific in your prompts. Instead of "a cat", try "a fluffy orange tabby cat wearing a top hat and monocle". 
- Experiment with different LoRAs to find styles you love. 
- If you're not happy with the result, try regenerating or adjusting your prompt and options. 
- Remember, the AI is creative but not perfect. Sometimes unexpected results can lead to exciting new ideas! 

#### Have Fun! 
The most important rule is to have fun and let your imagination run wild! Every prompt is an adventure, and you never know what amazing images you might create. Happy generating!


## Troubleshooting 
Encountering issues? Don't worry! Here are some common problems and simple solutions to get you back to creating amazing images. 

### Hardware Requirements For the best experience, we recommend:
 -  CPU: Recent Intel or AMD processor 
 -  RAM: 64GB of system memory 
 -  GPU: NVIDIA RTX 3090 or 4090 
 - While lower specifications may work, you might experience slower performance or limitations in image size and quality. If you have lower-end hardware: - You may need to adjust settings in ComfyUI to work with lower memory GPUs. - Check the [ComfyUI documentation](https://github.com/comfyanonymous/ComfyUI) for optimizations for lower-end hardware. 

### Common Issues 
1.  **Bot Not Responding** - Ensure the bot is online and has proper permissions in your Discord server. - Check if you're using the command in an allowed channel. 
2.  **Slow Image Generation** - This could be due to high server load or limited hardware resources. - Be patient, or try again at a less busy time. 
3.  **Error Messages** - If you see specific error messages, try restarting the bot. - Check the bot's console output for more detailed error information. 
4.  **Installation Problems** - Ensure you have Python 3.x installed correctly. - Verify that all dependencies are installed using `pip install -r requirements.txt`. 
5.  **GPU Not Detected** - Make sure you have the latest NVIDIA drivers installed. - Confirm that your GPU is CUDA-compatible and properly recognized by your system. 
6.  **Out of Memory Errors** - Try generating smaller images or using fewer LoRAs. - Close other resource-intensive applications on your system. 

### Still Having Trouble? If you're still experiencing issues: 
- Double-check all configuration settings in `.env`. 
- Ensure all required JSON files (`flux3.json`, `ratios.json`, `lora.json`) are present and correctly formatted. 
- Consult the ComfyUI documentation for advanced troubleshooting specific to the image generation backend.
		- There are options to use lowvram for comfyui this may allow it to work on 4070's 4060's and AMD GPUs with less that 24GB of VRam.  

Remember, running AI image generation can be resource-intensive. If you're consistently having issues, you might need to consider upgrading your hardware or optimizing your setup. For further assistance, don't hesitate to reach out. 

## Upcoming Features:
 -slash command to install loras from civitai - requires token for their api. it will download and place it in your comfyui /models/Lora folder and add it to the lora.json file. still limited to 25 loras.
    - refactoring lora.json and number entries to keep track of how many loras there are. 

## Contributing 
We welcome contributions to improve and expand this Discord Image Generation Bot! If you're interested in contributing, please follow these guidelines: 
1. Fork the repository and create your branch from `main`.
2. Make your changes, ensuring they adhere to the existing code style. 
3. Test your changes thoroughly. 
4. Create a pull request with a clear description of your improvements. For major changes or new features, please open an issue first to discuss what you would like to change. This ensures your time is well spent and your contributions align with the project's direction. 

If you encounter any bugs or have feature suggestions, please open an issue in the GitHub repository. For any questions or further information about contributing, please contact: Jerrod Linderman Email: nvmaxx@gmail.com We appreciate your interest in making this bot even better!

## License This project is dual-licensed: 
1. For non-commercial use, this software is licensed under the MIT License (see below). 
2. For commercial use, please contact Jerrod Linderman at nvmaxx@gmail.com to obtain a commercial license. 


## License 
Copyright (c) [2024] Jerrod Linderman 

This software is provided under a dual license model designed to meet the needs of both non-commercial and commercial users. 

### Non-Commercial Use License Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated documentation files (the "Comfyui Discord Bot"), to use, copy, modify, merge, publish, and distribute the Software for non-commercial purposes only, subject to the following conditions: 
1. The above copyright notice and this permission notice shall be included in all copies or substantial portions of the Software. 
2. The Software may not be used for commercial purposes, including but not limited to: - Selling the Software or derivatives of it - Using the Software to provide paid services - Incorporating the Software into a product that generates revenue 
3. Redistributions of the Software must retain this license notice and may not alter the terms for further redistribution. 

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

### Commercial Use 

For any commercial use of this Software, including but not limited to selling the Software, using it to provide paid services, or incorporating it into revenue-generating products, please contact Jerrod Linderman at nvmaxx@gmail.com to obtain a separate commercial license. By using this Software, you agree to abide by the terms of this licensing arrangement. Unauthorized commercial use of this Software is strictly prohibited and may result in legal action.

