import aiohttp
import asyncio
import pandas as pd
import os
from common.my_logger import logger
from reshape_data import ReshapeData
from brokers import Broker

config_dir = os.path.realpath('../') + '/config/'


class Kite(Broker):

    def __init__(self, userid: str, token: str, ticks: dict):
        super().__init__(userid, token, ticks)
        self.name = 'kite'
        self.base_url = 'https://kite.zerodha.com/oms/'
        self.saved_data = {}
        self.rd = ReshapeData(broker=f'{self.name}:{self.userid}', ticks=self.ticks, )

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

    async def limits(self, validation_call=False):
        return await self.get_response(path="user/margins", validation_call=validation_call)

    async def funds(self):
        return await self.get_response(path="funds")

    async def margin_book(self):
        margins = await self.limits()

        if margins is not None and margins['status'] == 'success':
            margins = margins['data']
            available = margins['equity']['net']
            used = margins['equity']['utilised']['debits']
            cash = margins['equity']['available']['cash'] + margins['equity']['available']['intraday_payin']
            total = available + used
            self.saved_data['max_margin_used'] = max(self.saved_data.get('max_margin_used', 0.0), used)

            return self.rd.margin_book(
                {
                    'used': used,
                    'max_used': self.saved_data['max_margin_used'],
                    'available': available,
                    'total': total,
                    'cash': cash
                })

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
