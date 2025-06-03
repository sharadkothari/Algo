import pandas as pd
from py_vollib.black_scholes.greeks.analytical import delta
import numpy as np
import json


class ReshapeData:
    def __init__(self, broker, ticks):
        self.broker = broker
        self.ticks = ticks
        self.tick_columns = ['last_price', 'timestamp', 'underlying', 'expiry_date', 'strike', 'opt_type']

    def extract_tick_fields(self, symbol_key):
        tick = self.ticks.get(symbol_key, {})
        if not isinstance(tick, dict):
            tick = json.loads(tick)
        return pd.Series({col: tick.get(col) for col in self.tick_columns})

    def safe_compute_delta(self, row):
        spot_price = self.ticks.get(row.underlying, {}).get('last_price', np.nan)
        try:
            return delta(
                flag=row['opt_type'][0].lower(),  # 'c' or 'p'
                S=spot_price,  # current spot price
                K=row['strike'],  # strike price
                t=row['dte_hours'] / (365 * 24),  # dte in hours -> years
                r=0.06,  # annualized risk-free rate
                sigma=0.18  # annualized implied volatility
            )
        except Exception:
            return np.nan

    def position_book(self, df):

        # -------- Step 1: Add Tick Data --------
        df['symbol_key'] = df['exch'] + ':' + df['symbol']
        df[self.tick_columns] = df['symbol_key'].apply(self.extract_tick_fields)

        # -------- Step 2: Net Qty and Current Amount --------
        df['net_qty'] = df['buy_qty'] - df['sell_qty']
        df['cur_amt'] = df['net_qty'] * df['last_price']

        # -------- Step 3: Net Premium --------
        df['net_amt'] = df['buy_amt'] - df['sell_amt']

        # -------- Step 4: MTM --------
        df['mtm'] = df['cur_amt'] - df['net_amt']

        # -------- Step 5: DTE --------
        # Time to expiry in **fraction of a year** (hours converted)
        df['expiry_datetime'] = pd.to_datetime(df['expiry_date']) + pd.Timedelta(hours=15, minutes=30)
        now = pd.Timestamp.now()
        df['dte_hours'] = (df['expiry_datetime'] - now).dt.total_seconds() / 3600

        # -------- Step 6: Delta Exposure --------
        df['delta'] = df.apply(self.safe_compute_delta, axis=1)
        df['delta_exposure'] = df['net_qty'] * df['delta']
        # -------- Step 11: Summary per Broker --------
        summary = {
            'timestamp': pd.Timestamp.now().isoformat(),
            'Broker': self.broker,
            'PE_Qty': int(df.loc[df['opt_type'] == 'PE', 'net_qty'].sum()),
            'CE_Qty': int(df.loc[df['opt_type'] == 'CE', 'net_qty'].sum()),
            'Premium': float(df['cur_amt'].sum()),
            'MTM': float(df['mtm'].sum()),
            'Pos_Delta': float(df['delta_exposure'].sum()),
        }
        return summary

    def margin_book(self, mb: dict):
        def format_number(number):
            return f'{number / 100000:6.1f}L'

        return {
            'timestamp': pd.Timestamp.now().isoformat(),
            'Broker': self.broker,
            'Total': format_number(mb['total']),
            'Used': f"{mb['used'] / mb['total'] * 100:.2f}%",
            'Max': f"{mb['max_used'] / mb['total'] * 100:.2f}%",
            'Bal': format_number(mb['available']),
            'Cash': format_number(mb['cash'])
        }
