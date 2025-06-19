# Telegram YouTube Downloader Bot

A Telegram bot that can download YouTube videos and extract audio in MP3 format.

## Features

- 🎥 Download YouTube videos in various qualities
- 🎵 Extract audio from YouTube videos (MP3 format)
- 📱 Easy-to-use Telegram interface
- ⚡ Fast download and processing
- 🔊 Support for video with separate audio tracks

## Requirements

- Python 3.8+
- FFmpeg (for audio extraction and video merging)
- Python packages (see requirements.txt)

## Installation

1. Clone this repository
```bash
git clone [your-repo-url]
cd telegram-youtube-bot
```

2. Create virtual environment
```bash
python -m venv tg_env
source tg_env/bin/activate  # On Windows: tg_env\Scripts\activate
```

3. Install dependencies
```bash
pip install -r requirements.txt
```

4. Install FFmpeg
- Download from [ffmpeg.org](https://ffmpeg.org/download.html)
- Add to system PATH

## Usage

1. Start the bot
```bash
python main.py
```

2. In Telegram:
- Start chat with bot
- Send YouTube link
- Choose video or audio
- Select quality (for video)
- Wait for download

## License

This project is open source and available under the MIT License. 