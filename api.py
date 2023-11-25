import bale
import requests
from bale import Bot

import config
    

class Client:
    def __init__(self, app: Bot):
        self.app = app
        self.loop = app.loop
        self.url = f"https://tapi.bale.ai/bot{config.TOKEN}/"

    async def get_chat(self, chat_id: str | int) -> bale.Chat:
        request = await self.loop.run_in_executor(None,
                                                  requests.get,
                                                  self.url + f"getChat?chat_id={chat_id}"
                                                  )
        return bale.Chat.from_dict(request.json()["result"], self.app) \
            if request.status_code == 200 else False

    async def get_chat_member(self, chat_id: str | int, user_id: str | int) -> bale.ChatMember:
        request = await self.loop.run_in_executor(None,
                                                  requests.get,
                                                  self.url + f"getChatMember?chat_id={chat_id}&user_id={user_id}"
                                                  )
        return bale.ChatMember.from_dict(chat_id, request.json()["result"], self.app) \
            if request.status_code == 200 else False
