# Geoffrey Bot

A Telegram bot for downloading and managing media files.

## Features

- 📥 Download media files (videos, music, documents)
- 📂 List downloaded files by type
- 🚦 Queue system for multiple downloads
- 📊 Download progress bar with speed indicator
- 🔒 User access control via Telegram ID

## Requirements

- Python 3.7 or higher
- Telegram Developer Account
- Telegram Bot Token

## Installation

1. Clone the repository:
   ```bash
   git clone [REPOSITORY_URL]
   cd geoffrey_telegram
   ```

2. Create a virtual environment (recommended):
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows: venv\Scripts\activate
   ```

3. Install dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Configuration

1. Create a `.env` file in the root directory with the following variables:
   ```env
   API_ID=your_api_id
   API_HASH=your_api_hash
   TELEGRAM_BOT_TOKEN=your_bot_token
   ALLOWED_USERS=your_telegram_id,another_id
   DOWNLOAD_PATH=/path/to/downloads
   ```

2. To get your Telegram user ID, you can use [@userinfobot](https://t.me/userinfobot)

## Usage

### Available Commands

- `/start` or `/help` - Show help menu
- `/list video` or `/l video` - List video files
- `/list music` or `/l music` - List music files
- `/list document` or `/l document` - List documents

### How to Use

1. Start the bot:
   ```bash
   python geoffrey_bot.py
   ```

2. Send any media file to the bot to download it.

3. Use commands to list downloaded files.

## File Structure

```
geoffrey_telegram/
├── geoffrey_bot.py    # Main bot code
├── requirements.txt   # Dependencies
├── .env.example      # Example configuration
└── downloads/        # Download directory (auto-created)
    ├── Video/        # Downloaded videos
    ├── Music/        # Music files
    └── Documents/    # Documents
```

## Notes

- The bot only processes files from authorized users (defined in `ALLOWED_USERS`)
- Downloads are automatically queued
- Download speed is shown in MB/s
- Files are saved in subdirectories based on their type

## Troubleshooting

If you encounter any issues:
1. Verify all environment variables are set correctly
2. Ensure you have write permissions in the download directory
3. Check the bot logs for error messages

## License

[MIT License](LICENSE)