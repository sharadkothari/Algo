import pandas as pd
from reshape_data import ReshapeData
from brokers import Broker


class Neo(Broker):
    def __init__(self, userid: str, token: str, ticks: dict):
        super().__init__(userid, token, ticks)
        self.name = "neo"
        self.base_url = 'https://mis.kotaksecurities.com/quick/user/'
        self.alt_url = 'https://neo.kotaksecurities.com/api/portfolio/v2/'  #method = get, for holdings
        self.rd = ReshapeData(broker=f'{self.name}:{self.userid}', ticks=self.ticks, )
        self.saved_data = {'max_margin_used': 0}

    async def holdings(self):
        # need alt_url
        return await self.get_response(path="holdings")

    async def limits(self, validation_call=False):
        return await self.get_response(path='limits', validation_call=validation_call)

    async def orders(self):
        return await self.get_response(path='orders')

    async def positions(self):
        return await self.get_response(path='positions')

    async def margin_book(self):
        limits = await self.limits()

        if limits is not None and 'MarginUsed' in limits:
            used = float(limits.get('MarginUsed', 0.1))
            available = float(limits.get('Net', 0.1))
            self.saved_data['max_margin_used'] = max(self.saved_data.get('max_margin_used', 0.0), used)

            margin_book = self.rd.margin_book({
                'used': used,
                'max_used': self.saved_data['max_margin_used'],
                'available': available,
                'total': used + available,
                'cash': float(limits.get('CollateralValue', 0.1))
            })
            self.saved_data.update({
                'max_margin_used': max(self.saved_data.get('max_margin_used', 0.0), used),
                'margin_used': margin_book['Used'],
            })
            return margin_book

    async def order_book(self):
        ob = []
        fields = ['ordSrc', 'actId', 'ordDtTm', 'nOrdNo', 'trdSym', 'trnsTp',
                  'qty', 'fldQty', 'unFldSz', 'prcTp', 'trgPrc', 'prc', 'avgPrc',
                  'ordSt']
        orders = await self.orders()
        if orders is not None:
            return pd.DataFrame(orders['data'], columns=fields)

    async def position_book(self):
        columns = {'trdSym': 'symbol', 'exSeg': 'exch',
                   'flBuyQty': 'buy_qty', 'buyAmt': 'buy_amt',
                   'flSellQty': 'sell_qty', 'sellAmt': 'sell_amt'}
        exch_map = {'bse_fo': 'BFO', 'nse_fo': 'NFO'}
        positions = await self.positions()
        if positions is not None and 'data' in positions:
            df = pd.DataFrame(positions.get('data', {}), columns=list(columns))
            df[list(columns)[2:]] = df[list(columns)[2:]].apply(pd.to_numeric)
            df.rename(columns=columns, inplace=True)
            df.replace({"exch": exch_map}, inplace=True)
            position_book = self.rd.position_book(df)
            position_book["Margin_Used"] = self.saved_data.get('margin_used')
            return position_book
