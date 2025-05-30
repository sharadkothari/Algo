import json
import aiohttp
import asyncio
import pandas as pd
import datetime
import os
from common.config import get_redis_client_async
from collections.abc import Coroutine
from common.my_logger import logger
from reshape_data import ReshapeData

config_dir = os.path.realpath('../') + '/config/'


class Kite:

    def __init__(self, userid: str, authorisation: str, ticks: dict):
        self.name = 'kite'
        self.userid = userid
        self.authorization = authorisation
        self.ticks = ticks
        self.base_url = 'https://kite.zerodha.com/oms/'
        self.saved_data = {}
        self.rd = ReshapeData(broker = f'{self.name}:{self.userid}', ticks = self.ticks, )

    @classmethod
    async def create(cls, userid: str, ticks: dict):
        r = await get_redis_client_async()
        token = await r.hget("browser_token", userid.lower())
        return cls(userid, token, ticks)

    async def get_token(self):
        r = await get_redis_client_async()
        return await r.hget("browser_token", self.userid.lower())

    def headers(self):
        return {
            'authorization': self.authorization
        }

    async def get_response(self, path, params=None):
        timeout = aiohttp.ClientTimeout(total=3)
        async with aiohttp.ClientSession(headers=self.headers(), timeout=timeout) as session:
            try:
                async with session.get(f'{self.base_url}{path}', params=params) as response:
                    if response.status == 200:
                        return await response.json()
                    else:
                        logger.info(f"Non-200 status for {path}: {response.status}")
            except asyncio.TimeoutError:
                logger.info(f"Timeout fetching {path}")
            except Exception as e:
                logger.info(f"Error fetching {path}: {e}")

    async def holdings(self):
        return await self.get_response(path="portfolio/holdings")

    async def mf_holdings(self):
        return await self.get_response(path="mf/holdings")

    async def positions(self):
        return await self.get_response(path="portfolio/positions")

    async def orders(self):

        return await self.get_response(path="orders")

    async def trades(self):
        return await self.get_response(path="trades")

    async def margins(self):
        return await self.get_response(path="user/margins")

    async def funds(self):
        return await self.get_response(path="funds")

    async def margin_book(self):
        margins = await self.margins()

        if margins is not None and margins['status'] == 'success':
            margins = margins['data']
            available = margins['equity']['net']
            used = margins['equity']['utilised']['debits']
            cash = margins['equity']['available']['cash'] + margins['equity']['available']['intraday_payin']
            total = available + used
            self.saved_data['max_margin_used'] = max(self.saved_data.get('max_margin_used', 0.0), used)

            return {
                'used': used,
                'max_used': self.saved_data['max_margin_used'],
                'available': available,
                'total': total,
                'cash': cash
            }

    async def position_book(self):
        columns = {'tradingsymbol': 'symbol', 'exchange': 'exch',
                   'buy_quantity': 'buy_qty', 'buy_value': 'buy_amt',
                   'sell_quantity': 'sell_qty', 'sell_value': 'sell_amt'}
        positions = await self.positions()
        if positions is not None and 'data' in positions and len(positions['data']['net']) > 0:
            df = pd.DataFrame(positions['data'].get('net', {}), columns=list(columns))
            df[list(columns)[2:]] = df[list(columns)[2:]].apply(pd.to_numeric)
            df.rename(columns=columns, inplace=True)
            return self.rd.position_book(df)

    async def portfolio(self):
        eq_holdings = await self.holdings()
        mf_holdings = await self.mf_holdings()
        df_list = []
        if eq_holdings is not None and 'data' in eq_holdings:
            eq_columns = {
                'tradingsymbol': 'symbol',
                'isin': 'isin',
                'opening_quantity': 'quantity',
                'last_price': 'last_price',
            }
            df_eq = pd.DataFrame(eq_holdings['data'], columns=list(eq_columns))
            df_eq.rename(columns=eq_columns, inplace=True)
            df_eq['value'] = df_eq['last_price'] * df_eq['quantity']
            df_list.append(df_eq)

        if mf_holdings is not None and 'data' in mf_holdings:
            mf_columns = {
                'tradingsymbol': 'isin',
                'fund': 'symbol',
                'quantity': 'quantity',
                'last_price': 'last_price',
            }
            df_mf = pd.DataFrame(mf_holdings['data'], columns=list(mf_columns))
            df_mf.rename(columns=mf_columns, inplace=True)
            df_mf['value'] = df_mf['quantity'] * df_mf['last_price']
            df_list.append(df_mf)

        return pd.concat(df_list, ignore_index=True)

    async def order_book(self):
        ob_columns = {
            'order_id': 'order_id', 'status': 'status', 'exchange_timestamp': 'timestamp',
            'exchange': 'exchange', 'tradingsymbol': 'tradingsymbol', 'order_type': 'order_type',
            'transaction_type': 'transaction_type', 'status_message': 'status_message',
            'quantity': 'quantity', 'average_price': 'average_price', 'filled_quantity': 'filled_quantity',
        }
        orders = await self.orders()
        if orders is not None and 'data' in orders:
            df_ob = pd.DataFrame(orders['data'], columns=list(ob_columns))
            df_ob.rename(columns=ob_columns, inplace=True)
            return df_ob
