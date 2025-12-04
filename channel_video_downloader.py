import os
import sys
import re
from telethon import TelegramClient, events, sync
import textwrap

from dataclasses import dataclass

if os.getenv('DEVELOPMENT'):
    from dotenv import load_dotenv
    load_dotenv()


@dataclass
class TelegramChannelVideoDownloader:
    session: str
    download_path: str
    API_ID: int = int(os.getenv('API_ID', '0'))
    API_HASH: str = os.getenv('API_HASH', '')
    BOT_TOKEN: str = os.getenv('TELEGRAM_BOT_TOKEN', '')
    ID_CHANNEL: str = os.getenv('', '')

    def __post_init__(self):
        print(os.getenv('API_ID'))
        print(os.getenv('API_HASH'))
        print(os.getenv('TELEGRAM_BOT_TOKEN', ''))

        self.client = TelegramClient(
            self.session, self.API_ID, self.API_HASH)
        self.bot_client = TelegramClient(
            'geoffrey', self.API_ID, self.API_HASH).start(bot_token=self.BOT_TOKEN)

    def download_progress(self, received_bytes, total):
        bar_length = 20
        percent = float(received_bytes) / total
        hashes = '#' * int(round(percent * bar_length))
        spaces = ' ' * (bar_length - len(hashes))
        sys.stdout.write("\rPercent: [{0}] {1}%".format(
            hashes + spaces, int(round(percent * 100))))
        sys.stdout.flush()

    def send_status_message(self, message):
        return
        with self.bot_client as client:
            client.send_message('toodaniels', message)

    def define_file_name(self, title):
        title = title.strip()\
            .replace('\n', ' ').replace(' ', '_').replace('/', '-')
        title = re.sub(r'[^a-zA-Z0-9._-]', '_', title)
        title = re.sub(r'_+', '_', title)
        return title

    def download_message_media(self, message):
        print(f'Message ID: {message.id} Media: {message.media}')
        if message.media.document:
            filename = message.media.document.attributes[1].file_name
        title = self.define_file_name(filename)
        self.send_status_message(f'Downloading {title} chat_id {message.id}')
        print(f'\nDownloading {title} chat_id {message.id}')
        print(f'Download path: {self.download_path + title}')
        try:
            message.download_media(
                self.download_path + title,
                progress_callback=self.download_progress
            )
        except Exception as e:
            self.send_status_message(f'Fail Downloading {title} error: {str(e)}')
        self.send_status_message(f'Downloaded {title}')

    def download_messages(self, chat_id, limit=200, min_id=None):
        print(f'Starting download messages from chat_id: {chat_id} limit: {limit} min_id: {min_id}')
        with self.client as client:
            messages = client.get_messages(
                chat_id, limit=limit, min_id=min_id, reverse=True)
            print(f'Found {len(messages)} messages to download')

            messages_ids = list(map(lambda message: message.id, messages))
            for message_id in messages_ids:
                self.download_message(chat_id, message_id)

    def download_message(self, chat_id, message_id):
        with self.client as client:
            message = client.get_messages(
                chat_id, limit=1, ids=message_id)
            # print(message)
            self.download_message_media(message)

    def search_message_by_text(self, chat_id, text):
        with self.client as client:
            messages = client.get_messages(chat_id, search=text, limit=10)

            for i, message in enumerate(messages):
                print(f'{i} Found message ID: {message.id} Text: {message.text}')

            if len(messages) > 1 or len(messages) == 0: 
                raise ValueError(
                    f'{len(messages)} matches of messages were found.')
            message = messages.pop()
            message_id = message.id
            message_text = textwrap.shorten(
                message.text, width=30, placeholder="...")

            print(f'ID Message found: {message_id} with text: {message_text}')
            return message_id

    def get_dialogs(self, id=None, title=None):
        with self.client as client:
            dialogs = client.get_dialogs()

            for dialog in dialogs:

                if dialog.is_channel \
                    and dialog.id == id:
                    print(f'Found dialog by id: {dialog.title} id: {dialog.id}')
                    return dialog.entity
                
    def get_me_channel(self):
        print('Getting me channel')
        with self.client as client:
            me = client.get_me()
            return me


def main():
    # chat_id = sys.argv[1]
    # limit = int(sys.argv[2])
    # seach_text = sys.argv[3]

    downloader = TelegramChannelVideoDownloader(
        session='max',
        download_path=os.getenv('DOWNLOAD_PATH'))
    
    me_channel = downloader.get_me_channel()

    # entity = downloader.get_dialogs(chat_id)
    # print(entity)

    message_id = downloader.search_message_by_text(me_channel.id, text='Dreamer')
    print(f'Message ID found: {message_id}')
    downloader.download_message(me_channel.id, message_id)

if __name__ == '__main__':
    main()