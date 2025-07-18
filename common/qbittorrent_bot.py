from common.telegram_bot import TelegramBot
from common.config import server_url
import requests

class QbittorrentBot(TelegramBot):
    consumer_name = "stocks"
    chat_id = -1002787848592

    def __new__(cls, send_only=True):
        return super().__new__(cls, cls.chat_id, cls.consumer_name, send_only=send_only)

    def __init__(self, send_only=True):
        super().__init__(chat_id=self.chat_id, consumer_name=self.consumer_name, send_only=send_only)
        self.base_url = f"{server_url}:8080/api/v2"
        self.session = requests.Session()
        self.set_session()

    def set_session(self):
        self.session.post(f"{self.base_url}/auth/login", data={
            "username": "sharadk",  "password": "qb1234"})

    def process_messages(self, message):
        ...

    def completed(self):
        r = self.session.get(f"{self.base_url}/torrents/info", params={"filter": "completed"})
        return r.json()

'''
Telegram Command	Action
/add <magnet-link>	Add torrent to qBittorrent
/status	List active downloads
/delete <hash>	Remove torrent with given info hash
/list	List completed torrents
/files <hash>	Get file list of torrent
'''



if __name__ == "__main__":
    q = QbittorrentBot()