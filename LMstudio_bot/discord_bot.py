import os
import discord
from discord import app_commands
from discord.ui import Modal, TextInput, Button, View
from dotenv import load_dotenv
from lora_manager.prompt_enhancer import PromptEnhancer
import json
import requests
from ai_providers import AIProviderFactory
import asyncio

# Load environment variables
load_dotenv()

class CopyButton(Button):
    def __init__(self, prompt: str):
        super().__init__(label="Copy Enhanced Prompt", style=discord.ButtonStyle.primary, custom_id="copy_prompt")
        self.prompt = prompt

    async def callback(self, interaction: discord.Interaction):
        try:
            # Create a new message with the prompt in a code block
            copy_message = (
                "Here's your enhanced prompt:\n"
                f"```\n{self.prompt}\n```"
            )
            
            # Send as an ephemeral message
            await interaction.response.send_message(copy_message, ephemeral=True)
        except Exception as e:
            await interaction.response.send_message(f"Failed to copy prompt: {str(e)}", ephemeral=True)

class LoraBot(discord.Client):
    def __init__(self):
        super().__init__(intents=discord.Intents.default())
        self.tree = app_commands.CommandTree(self)
        self.prompt_enhancer = PromptEnhancer()
        with open('LMlora.json', 'r') as f:
            self.lora_info = json.load(f)
        
        # Initialize AI provider as None - will be set after selection
        self.ai_provider = None

    async def check_lmstudio_available(self):
        """Check if LMStudio is accessible."""
        try:
            provider = AIProviderFactory.get_provider("lmstudio")
            return await provider.test_connection()
        except Exception as e:
            print(f"LMStudio check failed: {e}")
            return False

    async def check_openai_available(self):
        """Check if OpenAI is properly configured."""
        try:
            provider = AIProviderFactory.get_provider("openai")
            return await provider.test_connection()
        except Exception as e:
            print(f"OpenAI check failed: {e}")
            return False

    async def check_xai_available(self):
        """Check if X.AI is properly configured."""
        try:
            provider = AIProviderFactory.get_provider("xai")
            return await provider.test_connection()
        except Exception as e:
            print(f"X.AI check failed: {e}")
            return False

    async def prompt_provider_selection(self):
        """Prompt user to select AI provider and initialize it."""
        available_providers = []
        
        print("\nChecking available AI providers...")
        
        if await self.check_lmstudio_available():
            available_providers.append("lmstudio")
            print("✓ LM Studio is available")
        else:
            print("✗ LM Studio is not available")
            
        if await self.check_openai_available():
            available_providers.append("openai")
            print("✓ OpenAI is available")
        else:
            print("✗ OpenAI is not configured or API key is invalid")

        if await self.check_xai_available():
            available_providers.append("xai")
            print("✓ X.AI is available")
        else:
            print("✗ X.AI is not configured or API key is invalid")

        if not available_providers:
            print("\n⚠️ No AI providers are available. Please check your configuration.")
            return False

        if len(available_providers) == 1:
            selected = available_providers[0]
            print(f"\nAutomatically selecting the only available provider: {selected}")
        else:
            print("\nMultiple providers available. Please select one:")
            for i, provider in enumerate(available_providers, 1):
                print(f"{i}. {provider}")
                if provider == "lmstudio":
                    print("   (Local LM Studio server)")
                elif provider == "openai":
                    print("   (OpenAI GPT API)")
                elif provider == "xai":
                    print("   (X.AI API)")
            
            while True:
                try:
                    choice = input("\nEnter the number of your choice (1-{}): ".format(len(available_providers)))
                    index = int(choice) - 1
                    if 0 <= index < len(available_providers):
                        selected = available_providers[index]
                        break
                    print("Invalid choice. Please try again.")
                except ValueError:
                    print("Please enter a valid number.")

        try:
            self.ai_provider = AIProviderFactory.get_provider(selected)
            print(f"\n✓ Successfully initialized {selected} provider")
            return True
        except Exception as e:
            print(f"\n⚠️ Failed to initialize {selected} provider: {e}")
            return False

    async def setup_hook(self):
        """Setup hook that runs before the bot starts."""
        if not await self.prompt_provider_selection():
            print("\nFailed to initialize any AI provider. The bot may not function correctly.")
        await self.tree.sync()

    async def check_ai_provider(self):
        """Check if the AI provider is properly configured and accessible."""
        if self.ai_provider is None:
            print("No AI provider initialized")
            return False
        try:
            return await self.ai_provider.test_connection()
        except Exception as e:
            print(f"AI provider check failed: {e}")
            return False

    async def check_lmstudio_connection(self):
        """Check if LMStudio is accessible."""
        try:
            host = os.getenv("LMSTUDIO_HOST")
            port = os.getenv("LMSTUDIO_PORT")
            response = requests.get(f"http://{host}:{port}/v1/models", timeout=5)
            return response.status_code == 200
        except:
            return False

class PromptModal(Modal, title='Lora Enhancer'):
    prompt_input = TextInput(
        label='Enter your prompt',
        style=discord.TextStyle.paragraph,
        placeholder='Type your prompt here...',
        required=True,
    )
    
    count_input = TextInput(
        label='Number of LoRAs to find (1-5)',
        style=discord.TextStyle.short,
        placeholder='How many top matching LoRAs to find',
        required=True,
        max_length=1,
    )
    
    creativity_input = TextInput(
        label='Creativity level (1-10)',
        style=discord.TextStyle.short,
        placeholder='Enter a number between 1 and 10',
        required=True,
        max_length=2,
    )

    def __init__(self, client: LoraBot):
        super().__init__()
        self.client = client

    async def on_submit(self, interaction: discord.Interaction):
        try:
            # Check AI provider connection first
            if not self.client.ai_provider:
                await interaction.response.send_message(
                    "⚠️ Error: No AI provider initialized. Please restart the bot and select a provider.",
                    ephemeral=True
                )
                return
                
            if not await self.client.check_ai_provider():
                await interaction.response.send_message(
                    "⚠️ Error: Cannot connect to AI provider. Please check your configuration and ensure the selected provider is running.",
                    ephemeral=True
                )
                return
            
            try:
                count = int(self.count_input.value)
                creativity = int(self.creativity_input.value)
            except ValueError:
                await interaction.response.send_message(
                    "Please enter valid numbers for count and creativity level.",
                    ephemeral=True
                )
                return
            
            if not (1 <= count <= 5):
                await interaction.response.send_message("Number of LoRAs to find must be between 1 and 5.", ephemeral=True)
                return
                
            if not (1 <= creativity <= 10):
                await interaction.response.send_message("Creativity level must be between 1 and 10.", ephemeral=True)
                return

            await interaction.response.defer()

            try:
                # Removed the call to find_matching_loras as LoraSelector is removed
                # You may need to implement a different logic here
                pass

                # Format the response
                # enhanced_prompt = matches[0]['enhanced_prompt']
                
                # Create the response in a copyable format using Discord markdown
                # response = (
                #     f"Enhanced Prompt (Creativity Level {creativity}):\n"
                #     "📋 Click the box below to copy the prompt:\n"
                #     f"```\n{enhanced_prompt}\n```\n"
                #     "__________________________\n\n"
                #     "Matches:\n"
                # )
                
                # for i, match in enumerate(matches, 1):
                #     similarity = float(match['similarity_score'].rstrip('%'))
                #     if i == 1:
                #         response += f"Primary LoRA: {match['name']}, LoRA Match: {similarity:.2f}%\n"
                #     else:
                #         response += f"Lora {i}: {match['name']}, LoRA Match: {similarity:.2f}%\n"

                await interaction.followup.send("LoraSelector is removed. Please implement a different logic.")

            except Exception as e:
                await interaction.followup.send(f"An error occurred while processing your prompt: {str(e)}")

        except discord.errors.InteractionResponded:
            try:
                await interaction.followup.send(
                    "An error occurred while processing your request. Please try again.",
                    ephemeral=True
                )
            except:
                pass  # If even the followup fails, we can't do much

def run_bot():
    client = LoraBot()

    @client.event
    async def on_ready():
        print(f'Logged in as {client.user}')
        await client.tree.sync()
        
        # Check LMStudio connection on startup
        if not await client.check_lmstudio_connection():
            print("⚠️ Warning: Cannot connect to LMStudio server!")
            print(f"Make sure LMStudio is running at {os.getenv('LMSTUDIO_HOST')}:{os.getenv('LMSTUDIO_PORT')}")
        else:
            print("✅ Successfully connected to LMStudio server")

    client.run(os.getenv('DISCORD_TOKEN'))

if __name__ == "__main__":
    run_bot()
