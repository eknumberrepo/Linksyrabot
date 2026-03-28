import os
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("BOT_TOKEN")
CHANNEL_ID = int(os.getenv("CHANNEL_ID"))
CHANNEL_USERNAME = "@BotXHubz"

# Add your Telegram user ID for premium
PREMIUM_USERS = [1106857285]
