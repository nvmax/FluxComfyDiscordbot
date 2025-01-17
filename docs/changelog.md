# Changelog

## Latest Updates
#### New Features

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

### December 15, 2024
  **Banned words list**
  - Updated the banned words list to include a list of common profanities and sensitive terms to avoid discord flagging and banning.
  - User can add new words to the list or use the `/add_banned_word` command in discord to add words manually.
  - Remember USERS ARE 100% RESPONSIBLE FOR WHAT THEY POST IN DISCORD, Generated images that contain sensitive content may result in a permanent ban from discord.
  - Please make sure your users are well aware of the banned words list and discords policies.

### December 6, 2024
#### New Features
- **Flux Redux**
  - /redux command to generate an image using two reference images
  - /reduxprompt command to generate an image using a reference image and prompt
  - redux first image will be the main image, 2nd image is style reference 
  - reduxprompt image allows user to use a prompt to generate an image from a reference image with a style prompt 

  - **Various fixes and improvements**
  - resolved setup tool not saving server_address
  - expanded fields in setup tool to allow better view of servers and channels
  - fixed issues banned and why banned giving errors 
  

- **LMStudio / Ai Prompt Enhancements**
  - Now you can select LMStudio, xAI or OpenAI with in the setup tool
  - When generating prompts a modal will appear to select Creativity level
  - Creativity level can be adjusted from 1-10 with 1 not changing your prompt and 10 extremely creative.
  - can enable or disable AI Prompt Enhancements using the setup tool

- **Various fixes and improvements**
  - Added features to the setup tool for AI Prompt Enhancements
  - updated workflows in Datasets to support new clip models
  - updated Lora Editor and made it more user friendly and robust

#### Example of /redux command

<div style="display: flex; justify-content: center; flex-wrap: wrap; gap: 20px; margin: 20px 0;">
  <div style="text-align: center; border: 2px solid #ddd; border-radius: 10px; padding: 15px; background-color: #f8f9fa;">
    <h4 style="margin: 0 0 10px 0; color: #333;">Original Image</h4>
    <img src="redux1.png" alt="Original Image" width="600" style="border-radius: 5px;">
  </div>
  
  <div style="text-align: center; border: 2px solid #ddd; border-radius: 10px; padding: 15px; background-color: #f8f9fa;">
    <h4 style="margin: 0 0 10px 0; color: #333;">Style Reference</h4>
    <img src="redux2.png" alt="Style Reference" height="600" style="border-radius: 5px;">
  </div>
  
  <div style="text-align: center; border: 2px solid #ddd; border-radius: 10px; padding: 15px; background-color: #f8f9fa;">
    <h4 style="margin: 0 0 10px 0; color: #333;">Final Result</h4>
    <img src="redux3.png" alt="Final Result" width="600" style="border-radius: 5px;">
  </div>
</div>

### November 16, 2024
#### New Features
- **Enhanced LoRA Weight Management**
  - Automatic weight scaling for multiple LoRAs
  - Full weight utilization for single LoRA selections
  
- **LoRA Info Command**
  - Detailed information display
  - URL links to example images
  - Visual reference guides
  
- **Improved LoRA Editor**
  - Modernized user interface
  - Double-click editing functionality
  - Automatic save feature
  - Enhanced user experience

### November 11, 2024
#### Technical Updates
- **Numpy 2 Compatibility**
  - Fixed workflow loading errors
  - Modified file system for compatibility
  - Maintained backward compatibility
  
- **Setup Tool Improvements**
  - Added folder validation system
  - Enhanced base directory specification
  - Example path: `C:/Comfyui_windows_portable/ComfyUI`
  
- **Lora Monitor Enhancement**
  - Improved timing for LoRA list updates
  - Better update status verification
  - Enhanced reliability

## Previous Versions

### October 2024
[To be added]

### September 2024
[To be added]

---

## Update Notes
- All updates are tested thoroughly before release
- Backup your configurations before major updates
- Check compatibility with your current setup
