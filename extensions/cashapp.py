import asyncio
import ssl
import datetime
import pytz
import random
import re
import aiohttp
import time

with open('./proxies.txt', 'r') as proxies:
    proxies = [proxy.strip() for proxy in proxies]

class CashappAPI:
    @staticmethod
    def __construct_receipt__(__: str) -> str:
        if 'https://cash.app/payments' in __: return __
        if 'cash.app/payments' in __: return 'https://' + __.replace('http://', '')
        if len(__) == 25: return 'https://cash.app/payments/{}/receipt?utm_source=activity-item'.format(__)

    def __init__(self, proxy: str | dict | bool = None) -> None:
        self.proxy = 'htpp://' + random.choice(proxies) if proxy and proxies else None

    async def getQrCode(self, cashtag: str, size: int = 100, margin: int = 0) -> aiohttp.ClientResponse | None:
        async with aiohttp.ClientSession(connector = aiohttp.TCPConnector(ssl = False), headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json; charset=utf-8',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin'
        }) as session:
            return await session.get(
                'https://cash.app/qr/${}?size={}&margin={}'.format(cashtag.replace('$', ''), size, margin), proxy = self.proxy)

    async def getReceipt(self, receipt: str) -> tuple | None:
        receipt = CashappAPI.__construct_receipt__(receipt)
        if not receipt:
            return
        match = re.search(r'/payments/([^/]+)', receipt)
        if not match:
            return
        async with aiohttp.ClientSession(connector = aiohttp.TCPConnector(ssl = False), headers = {
            'Accept': 'application/json',
            'Content-Type': 'application/json; charset=utf-8',
            'sec-fetch-dest': 'empty',
            'sec-fetch-mode': 'cors',
            'sec-fetch-site': 'same-origin'
        }) as session:
            async with session.get('https://cash.app/receipt-json/f/{}'.format(match.group(1)), proxy = self.proxy) as response:
               json = await response.json()
               return (json, match.group(1))

class Time:
    def generateTimestamp() -> int:
        return int(datetime.datetime.now(pytz.timezone('America/Chicago')).timestamp())
      
    def getFutureTimestamp(timestamp, minutes) -> int:
        return int((datetime.datetime.fromtimestamp(timestamp, pytz.timezone('America/Chicago')) + datetime.timedelta(minutes = minutes)).timestamp())

    def withinTimeLimit(timestamp, user_timestamp, future_timestamp) -> bool:
        return timestamp < user_timestamp and user_timestamp < future_timestamp

async def __get_receipt__(receipt: str, proxy: str | dict | None = None) -> tuple:
    cashapp = CashappAPI(proxy)
    receipt = await cashapp.getReceipt(receipt)
    if not receipt:
       return ()
    
    timestamp_str = receipt[0]['details_view_content']['rows'][-1:][0]
    timestamp = (datetime.datetime.strptime(timestamp_str, '%b %d, %Y at %I:%M %p') + datetime.timedelta(hours = 2, minutes = 1)).timestamp()
    
    return (
       receipt[0]['title'],
       '$' + receipt[0]['header_subtext'].split('$')[1],
       float(receipt[0]['amount_formatted'].replace('$', '')),
       receipt[0].get('notes'),
       int(timestamp),
       receipt[0]['status_text'].title() == 'Sent',
       receipt[1]
    )  # Receiver, Receiver Cashtag, Amount, Note, Adjusted Timestamp, Completed, Receipt ID -- Broken?
