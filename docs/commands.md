# 📝 Commands Guide

## 🎨 Image Generation Commands

### `/comfy`
Generate images from text descriptions
```
/comfy [prompt] [resolution] [options]
```
Options:
- `resolution`: Choose image size (512x512, 768x768, etc.)
- `upscale factor`: Set upscaling factor
- `creativity`: Adjust creativity level (modal popup)
- `lora`: Apply LoRA models

### `/lorainfo`
View information about available LoRA models
```
/lorainfo 
```
- Displays a list of available LoRA models
- Click on Lora info to view details

### `other commands`   
- `/add_banned_word`: Add a banned word (admin only)
- `/remove_banned_word`: Remove a banned word (admin only)
- `/list_banned_words`: List banned words (all users)
- `/ban_user`: Ban a user from using the bot (admin only private message)
- `/unban_user`: Unban a user (admin only private message)
- `/list_banned_users`: List banned users (admin only private message) 
- `/check_warnings`: Check user warnings (admin only private message)
- `/remove_warning`: Remove a warning from a user (admin only private message)
- `/whybanned`: Check why a user is banned will give back the prompt they tried to use (admin only private message)
- `/reboot`: Reboot the bot (admin only)
- `/reload_options`: Reload bot options (admin only) ** depreciated should do this automatically**
- `/sync`: Sync the bot with discord if commands have not registered (admin only)


## 📊 Advanced Usage

### Combining LoRAs
When using multiple LoRAs:
- Single LoRA: Full weight applied
- Multiple LoRAs: Weights automatically balanced

### Resolution Guidelines
Larger resolution takes longer to generate.:
- you can select from a variety of resolutions
- consider the intended use and how they will impact the final result

## 🎯 Tips for Best Results

1. **Prompt Writing**
   - Be specific in descriptions
   - Use artistic terms
   - Include desired style

2. **LoRA Selection**
   - Choose complementary styles
   - Test different combinations

3. **Resolution Choice**
   - Match to intended use
   - Consider generation time
   - Balance quality vs speed

4. **Customization**
   - Experiment with creativity
     - creativity from 1-10 with 1 not changing your prompt and 10 extremely creative. 
   - Adjust upscaling factor
