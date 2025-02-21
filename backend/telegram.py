#!/usr/bin/env python3

import telethon
import logging
import time
from telethon import TelegramClient, events
from telethon.tl.functions.channels import GetFullChannelRequest
from worker import CollectorWorker, ConfigMissingException

logging.getLogger().setLevel(logging.DEBUG)

# --------------------------------------------------------------------------- #

class TelegramCollector(CollectorWorker):

    def __init__(self):
        super().__init__("Telegram")

        try:
            self.API_ID = self.get_config('API_ID')
            self.API_HASH = self.get_config('API_HASH')
            self.SESSION_PATH = self.get_config('SESSION_PATH')

            self.client = TelegramClient(self.SESSION_PATH, self.API_ID,
                                         self.API_HASH)
            self.client.on(events.NewMessage)(self.process_message)
        except Exception as err:
            self.on_error()
       
    # ----------------------------------------------------------------------- #

    def start(self):
        try:
            if not all([self.API_ID, self.API_HASH, self.SESSION_PATH]):
                logging.error("API_ID, API_HASH or SESSION_PATH configuration "
                              "variables are not set. Please set them then "
                              "restart the worker.")
                raise ConfigMissingException()
        except ConfigMissingException as err:
            self.on_error()

        while True:
            try:
                self.client.start()
                self.client.loop.run_until_complete(self.telegram_init())
                self.client.run_until_disconnected()
                raise Exception
            except Exception as err:
                self.on_error({'telegram_client': self.safe_str(self.client)})
                time.sleep(10)

    # ----------------------------------------------------------------------- #

    async def telegram_init(self):
        async for dialog in self.client.iter_dialogs():
            if isinstance(dialog.entity, telethon.tl.types.Channel):
                print(f"Channel ID: {dialog.entity.id}, "
                      f"Name: {dialog.entity.title}")
                self.add_channel(dialog.entity.title, str(dialog.entity.id),
                                 None, None)

    # ----------------------------------------------------------------------- #

    async def is_linked_supergroup(self, chat_id):
        """
        Returns True if the given chat_id belongs to a linked supergroup
        (discussion group of a channel).
        """
        try:
            chat = await self.client.get_entity(chat_id)
            if isinstance(chat, telethon.tl.types.Channel):
                full_channel = await self.client(GetFullChannelRequest(chat))
                if full_channel.full_chat.linked_chat_id:
                    return True
        except Exception as err:
            print(f"Failed to fetch linked chat for {chat_id}: {err}")
        return False

    # ----------------------------------------------------------------------- #

    async def process_message(self, event: telethon.events.NewMessage.Event):
        sender = await event.get_sender()
        chat = await event.get_chat()

        # Check if message is from a discussion group
        if await self.is_linked_supergroup(chat.id):
            # Allow only messages that are original posts, not user comments
            if not event.message.post:
                print(f"Ignoring user comment in linked supergroup: "
                      f"{chat.title} ({chat.id})")
                return

        if event.message and event.message.message:
            if len(event.message.message):
                try:
                    await self.print_message(event)

                    data = {
                        'id': event.message.id,
                        'message_text': event.message.message,
                    }

                    self.add_data(str(chat.id), data, event.message.message)
                except Exception as err:
                    self.on_error({'message_event': self.safe_str(event)})
 
    # ----------------------------------------------------------------------- #

    async def print_message(self, event):
        sender = await event.get_sender()

        # Message basic information
        logging.info(f"Message ID: {event.message.id}")
        logging.info(f"Date: {event.message.date}")
        logging.info(f"Message Text: {event.message.message}")

        # Chat/Channel information
        chat = await event.get_chat()
        if event.is_group or event.is_channel:
            logging.info(f"Chat/Channel ID: {chat.id}")
            logging.info(f"Chat/Channel Name: {chat.title}")
        else:
            logging.info("Private Message")

        # Sender information
        sender = await event.get_sender()
        logging.info(f"Sender ID: {sender.id}")
        logging.info(f"Sender Username: {sender.username}")

        # Media information (if any)
        if event.message.media:
            logging.info(f"Media: {event.message.media}")

        # Additional details
        logging.info(f"Is Private: {event.is_private}")
        logging.info(f"Is Group: {event.is_group}")
        logging.info(f"Is Channel: {event.is_channel}")
        logging.info(f"Forwarded: {event.message.fwd_from is not None}")

# --------------------------------------------------------------------------- #

def main():
    tc = TelegramCollector()
    tc.start()

# --------------------------------------------------------------------------- #
    
if __name__ == '__main__':
    main()

# --------------------------------------------------------------------------- #
