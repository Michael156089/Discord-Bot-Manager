import sys
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.manager_bot.main import bot, token

if __name__ == "__main__":
    if not token:
        print("Warning: Token not found. Using dummy token for testing.")
        token = "DUMMY_TOKEN"
    
    try:
        bot.run(token)
    except Exception as e:
        print(f"Bot stopped: {e}")