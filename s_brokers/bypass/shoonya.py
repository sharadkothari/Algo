import pandas as pd
import datetime
from common.expiry import Expiry
from reshape_data import ReshapeData
from brokers import Broker
import re


class Shoonya(Broker):

    def __init__(self, userid: str, token: str, ticks: dict):
        super().__init__(userid, token, ticks)
        self.name = 'shoonya'
        self.base_url = 'https://trade.shoonya.com/NorenWClientWeb/'
        self.saved_data = {'max_margin_used': 0}
        self.rd = ReshapeData(broker=f'{self.name}:{self.userid}', ticks=self.ticks, )

    async def holdings(self):
        return await self.get_response(path='Holdings', prd_key='C')

    async def orders(self):
        return await self.get_response(path='OrderBook', prd_key='C')

    async def positions(self):
        return await self.get_response(path='PositionBook', prd_key='C')

    async def trade_book(self):
        return await self.get_response(path='TradeBook', prd_key='C')

    async def limits(self, validation_call=False):
        return await self.get_response(path='Limits', prd_key=None, validation_call=validation_call)

    async def margin_book(self):
        limits = await self.limits()

        if limits is not None:
            used = float(limits.get('marginused', 0.1))
            self.saved_data['max_margin_used'] = max(self.saved_data.get('max_margin_used', 0.0), used)
            collateral = float(limits.get('collateral', 0.1))
            cash = float(limits.get('cash', 0.2)) + float(limits.get('payin', 0))
            total = collateral + cash

            margin_book = self.rd.margin_book({
                'used': used,
                'max_used': self.saved_data['max_margin_used'],
                'available': total - used,
                'total': total,
                'cash': cash
            })
            self.saved_data.update({
                'max_margin_used': max(self.saved_data.get('max_margin_used', 0.0), used),
                'margin_used': margin_book['Used'],
            })
            return margin_book

    async def position_book(self):
        columns = {'tsym': 'symbol', 'exch': 'exch',
                   'daybuyqty': 'buy_qty', 'daybuyamt': 'buy_amt',
                   'daysellqty': 'sell_qty', 'daysellamt': 'sell_amt'}
        positions = await self.positions()
        if type(positions) is list:
            for p in positions:
                if p.get('exch', None) == 'NFO':
                    p['tsym'] = nfo_symbol_reshape(p['tsym'])

        if positions is not None and type(positions) is list:
            df = pd.DataFrame(positions, columns=list(columns))
            df[list(columns)[2:]] = df[list(columns)[2:]].apply(pd.to_numeric)
            df.rename(columns=columns, inplace=True)
            position_book = self.rd.position_book(df)
            position_book["Margin_Used"] = self.saved_data.get('margin_used')
            return position_book

    async def order_book_eq(self):
        columns = {
            'tsym': 'symbol', 'exch': 'exch', 'exch_tm': 'timestamp',
            'trantype': 'tran_type', 'rejreason': 'reject_reason',
            'instname': 'inst_name', 'status': 'status',
            'avgprc': 'avg_price', 'fillshares': 'fill_shares',
            'qty': 'order_qty', 'prc': 'order_price'
        }
        orders = await self.orders()
        if orders is not None and type(orders) is list:
            df = pd.DataFrame(orders, columns=list(columns))
            df[list(columns)[-4:]] = df[list(columns)[7:]].apply(pd.to_numeric)
            df.rename(columns=columns, inplace=True)
            df['amt'] = df.fill_shares * df.avg_price
            return df

    async def order_book(self):

        columns = {
            'norenordno': 'order_id', 'status': 'status', 'exch_tm': 'timestamp',
            'exch': 'exchange', 'tsym': 'tradingsymbol', 'prctyp': 'order_type',
            'trantype': 'transaction_type', 'rejreason': 'status_message',
            'qty': 'quantity', 'avgprc': 'average_price', 'fillshares': 'filled_quantity',
        }
        tt_map = {'B': 'BUY', 'S': 'SELL'}
        orders = await self.orders()

        if orders is not None and type(orders) is list:
            df = pd.DataFrame(orders, columns=list(columns))
            df[list(columns)[-3:]] = df[list(columns)[-3:]].apply(pd.to_numeric)
            df.rename(columns=columns, inplace=True)
            df.replace({"trantype": tt_map}, inplace=True)
            return df


def nfo_symbol_reshape(symbol):
    # e.g. symbol = "BANKNIFTY08MAY24P48000"
    pattern = r"^([A-Z]+?)(\d{2}[A-Z]{3}\d{2})([A-Z])(\d+)$"
    match = re.match(pattern, symbol)
    if match:
        derivative_symbol = match.group(1)
        date_str = match.group(2)
        option_type = f'{match.group(3)}E'
        strike = int(match.group(4))
        exp = Expiry(f'{derivative_symbol[0]}N')
        exp_date = datetime.datetime.strptime(date_str, '%d%b%y').date()
        exp_str = exp.get_exp_str(exp_date)
        return f'{exp_str}{strike}{option_type}'
