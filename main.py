import logging
import os
import subprocess
import re
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    ApplicationBuilder, CommandHandler, MessageHandler, filters,
    CallbackQueryHandler, ContextTypes
)
from pytubefix import YouTube
import time

# Enable logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# Global variables
class UserState:
    def __init__(self):
        self.yt = None
        self.selected_stream = None
        self.url = None

user_states = {}

def sanitize_filename(filename):
    return re.sub(r'[<>:"/\\|?*]', "", filename)

def get_user_state(user_id: int) -> UserState:
    if user_id not in user_states:
        user_states[user_id] = UserState()
    return user_states[user_id]

def delete_file(file_path):
    """Delete the file if it exists."""
    if os.path.exists(file_path):
        os.remove(file_path)
        logger.info(f"File {file_path} deleted successfully.")
    else:
        logger.warning(f"File {file_path} not found, skipping deletion.")

async def start(update: Update, context):
    welcome_text = """
🎥 *YouTube Downloader Bot* 🎥

Send me a YouTube link, and I'll help you download:
• Video in various qualities
• Audio in MP3 format

*How to use:*
1. Paste a YouTube link
2. Choose video or audio
3. Select quality (for video)
4. Wait for download

Let's start! Send me a YouTube link 🔗
    """
    await update.message.reply_text(welcome_text, parse_mode='Markdown')

async def update_progress_message(message, status_text):
    try:
        await message.edit_text(status_text)
    except Exception as e:
        logger.error(f"Failed to update progress: {e}")

async def show_download_options(message, user_state: UserState):
    try:
        title = user_state.yt.title[:50] + "..." if len(user_state.yt.title) > 50 else user_state.yt.title
        text = f"📺 *{title}*\n\n" \
               f"⏱ Duration: {user_state.yt.length//60}:{user_state.yt.length%60:02d}\n" \
               f"👁 Views: {user_state.yt.views:,}\n\n" \
               f"Choose download format:"
        keyboard = [
            [InlineKeyboardButton(f"🎥 Download Video", callback_data="video")],
            [InlineKeyboardButton(f"🎵 Download Audio (MP3)", callback_data="audio")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        if isinstance(message, Update):
            await message.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        else:
            await message.edit_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    except Exception as e:
        logger.error(f"Error showing download options: {e}")
        error_text = f"❌ An error occurred. Please try again."
        if isinstance(message, Update):
            await message.message.reply_text(error_text)
        else:
            await message.edit_text(error_text)

async def handle_youtube_link(update: Update, context):
    user_id = update.effective_user.id
    user_state = get_user_state(user_id)
    if update.callback_query:
        url = user_state.url
        status_message = update.callback_query.message
        await status_message.edit_text("⏳ Analyzing video...")
    else:
        url = update.message.text.strip()
        user_state.url = url
        status_message = await update.message.reply_text("⏳ Analyzing video...")
    try:
        user_state.yt = YouTube(url)
        await show_download_options(status_message, user_state)
    except Exception as e:
        logger.error(f"Error: {e}")
        await status_message.edit_text("❌ Failed to process the video link. Please check the URL and try again.")

async def handle_download_option(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    user_state = get_user_state(user_id)
    if query.data == "video":
        streams = user_state.yt.streams.filter(file_extension="mp4").order_by("resolution").desc()
        if streams:
            keyboard = [[InlineKeyboardButton(f"🎥 {stream.resolution} ({stream.filesize_mb:.1f} MB)", callback_data=f"res_{i}")] 
                for i, stream in enumerate(streams)]
            keyboard.append([InlineKeyboardButton("↩️ Back", callback_data="back")])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await query.edit_message_text(
                "Select video quality:\n\nHigher quality = Larger file size",
                reply_markup=reply_markup
            )
        else:
            await query.edit_message_text("❌ No suitable video streams found.")
    elif query.data == "audio":
        await query.edit_message_text("⏳ Processing audio download.")
        await download_audio(update, context)
    elif query.data == "back":
        await show_download_options(query.message, user_state)

async def handle_resolution_selection(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user_id = update.effective_user.id
    user_state = get_user_state(user_id)
    try:
        if query.data == "back":
            await show_download_options(query.message, user_state)
            return
        if not query.data.startswith("res_"):
            return
        stream_index = int(query.data.replace("res_", ""))
        streams = user_state.yt.streams.filter(file_extension="mp4").order_by("resolution").desc()
        if not streams:
            raise Exception("No streams available")
        user_state.selected_stream = streams[stream_index]
        await query.edit_message_text("⏳ Starting download.")
        await download_video(update, context)
    except Exception as e:
        logger.error(f"Error in handle_resolution_selection: {str(e)}")
        await query.edit_message_text(f"❌ Failed to select resolution. Error: {str(e)}")

async def download_video(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state = get_user_state(user_id)
    status_message = update.callback_query.message
    download_path = None  # Initialize to track file path
    video_path = None
    audio_path = None
    try:
        if not user_state.selected_stream:
            raise Exception("No stream selected")
        await update_progress_message(status_message, "📥 Downloading...")
        filename = f"video_{user_id}_{int(time.time())}.mp4"
        download_path = os.path.join("downloads", filename)

        if user_state.selected_stream.is_progressive:
            download_path = user_state.selected_stream.download(
                output_path="downloads",
                filename=filename
            )
        else:
            video_stream = user_state.selected_stream
            audio_stream = user_state.yt.streams.filter(only_audio=True, file_extension="mp4").first()
            if not audio_stream:
                raise Exception("No audio stream found")
            video_path = video_stream.download(
                output_path="downloads",
                filename=f"video_{filename}"
            )
            audio_path = audio_stream.download(
                output_path="downloads",
                filename=f"audio_{filename}"
            )
            await update_progress_message(status_message, "⚙️ Processing...")
            download_path = os.path.join("downloads", f"final_{filename}")
            command = f'ffmpeg -i "{video_path}" -i "{audio_path}" -c:v copy -c:a aac "{download_path}"'
            process = subprocess.run(command, shell=True, capture_output=True, text=True)
            if process.returncode != 0:
                raise Exception(f"FFmpeg failed: {process.stderr}")
        await update_progress_message(status_message, "📤 Uploading...")
        with open(download_path, "rb") as video_file:
            await context.bot.send_video(
                chat_id=update.callback_query.message.chat_id,
                video=video_file,
                caption=f"🎥 {user_state.yt.title}\n🎬 {user_state.selected_stream.resolution}"
            )
        await update_progress_message(status_message, "✅ Complete.")
    except Exception as e:
        logger.error(f"Error in download_video: {str(e)}")
        await update_progress_message(status_message, f"❌ Failed.\nError: {str(e)}")
    finally:
        # Clean up all temporary files
        for path in [download_path, video_path, audio_path]:
            if path and os.path.exists(path):
                os.remove(path)
                logger.info(f"File {path} deleted successfully.")

async def download_audio(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    user_state = get_user_state(user_id)
    status_message = update.callback_query.message
    audio_path = None  # Initialize to track file path
    mp3_path = None
    try:
        await update_progress_message(status_message, "📥 Downloading...")
        audio_stream = user_state.yt.streams.filter(only_audio=True, file_extension="mp4").first()
        if not audio_stream:
            raise Exception("No audio stream found.")
        audio_path = audio_stream.download(output_path="downloads", filename_prefix="audio_")
        sanitized_title = sanitize_filename(user_state.yt.title)
        mp3_path = os.path.join("downloads", f"{sanitized_title}.mp3")
        await update_progress_message(status_message, "⚙️ Processing...")
        command = f'ffmpeg -i "{audio_path}" -q:a 0 -map a "{mp3_path}"'
        subprocess.run(command, shell=True, check=True)
        await update_progress_message(status_message, "📤 Uploading...")
        with open(mp3_path, "rb") as audio_file:
            await context.bot.send_audio(
                chat_id=update.callback_query.message.chat_id,
                audio=audio_file,
                title=user_state.yt.title,
                performer=user_state.yt.author,
                caption=f"🎵 {user_state.yt.title}"
            )
        await update_progress_message(status_message, "✅ Complete.")
    except Exception as e:
        logger.error(f"Error downloading audio: {e}")
        await update_progress_message(status_message, f"❌ Failed.\nError: {str(e)}")
    finally:
        # Clean up all temporary files
        for path in [audio_path, mp3_path]:
            if path and os.path.exists(path):
                os.remove(path)
                logger.info(f"File {path} deleted successfully.")

def main():
    application = ApplicationBuilder().token("7980188907:AAEq8sb95Tpsbx_uptW-UGI8sYlx3T0PcFg").read_timeout(36000).write_timeout(36000).build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_youtube_link))
    application.add_handler(CallbackQueryHandler(handle_download_option, pattern="^(video|audio|back)$"))
    application.add_handler(CallbackQueryHandler(handle_resolution_selection, pattern="^res_[0-9]+$"))
    application.run_polling()

if __name__ == "__main__":
    if not os.path.exists("downloads"):
        os.makedirs("downloads")
    main()
