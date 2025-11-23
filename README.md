# Bot Manager

**Created by: mk3ang8l**

## 🎯 Purpose
This bot is designed to help you **host and manage Discord bots** for other people. It's a complete system to:
-   **Sell hosting slots**: Users need a "secret key" to register.
-   **Rent scripts**: You can lock specific scripts behind a VIP status.
-   **Manage resources**: Automatically monitors CPU/RAM usage of user bots.

## 📜 License
This project is protected. All rights reserved by **mk3ang8l**.

## 🚀 Setup

1.  **Install Python** (3.8 or higher).
2.  **Install Dependencies**:
    ```bash
    pip install -r requirements.txt
    ```
3.  **Configure Environment**:
    - Rename `.env.example` to `.env` (if it exists) or create a new `.env` file.
    - Add your bot token:
      ```
      BOT_MANAGER_TOKEN=your_token_here
      ADMIN_IDS=123456789,987654321
      ```
4.  **Run the Bot**:
    ```bash
    python run.py
    ```

## 📜 Adding Scripts

You can offer different scripts to your users.

-   **Basic Scripts**: Place your `.py` files in:
    `src/manager_bot/admin_scripts/basic/`
    *These are available to everyone.*

-   **Premium Scripts**: Place your `.py` files in:
    `src/manager_bot/admin_scripts/premium/`
    *These are available only to VIP users or users granted specific access.*

## 🎮 Commands

### User Commands
-   `/help`: Show this help message.
-   `/register [secret]`: Create your account using a secret key.
-   `/add_bot [name] [token] [script]`: Add a new bot to host.
-   `/start_bot [name]`: Start one of your bots.
-   `/stop_bot [name]`: Stop one of your bots.
-   `/my_bots`: List your bots and their status.
-   `/bot_logs [name]`: View the latest logs from your bot.

### Admin Commands
-   `/create_secret [user_id] [max_bots]`: Generate a registration key.
-   `/list_users`: Show all registered users.
-   `/grant_script [user_id] [script]`: Give a user access to a premium script.
-   `/stats`: View server resource usage.

## 📁 Project Structure

-   `run.py`: Entry point.
-   `src/manager_bot/config.py`: Configuration settings.
-   `src/manager_bot/cogs/`: Bot commands (Admin, User, General).
-   `src/manager_bot/admin_scripts/`: Folder for your bot scripts.

## 💖 Support the Project

If you like this project and want to support its development, you can:
-   **Star** this repository on GitHub ⭐
-   **Donate** via [PayPal](https://www.paypal.me/MicaPaul138) or
-   **Crypto (USDT Tether)**: `0xed3b8597fbc4a8724907d1839ed465c19172ff5d`
-   Share it with your friends!
