import pandas as pd
import py_vollib_vectorized
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

    def compute_iv_and_delta(self, df):
        # Extract necessary columns
        spot_prices = df['underlying'].map(lambda x: self.ticks.get(x, {}).get('last_price', np.nan))
        option_prices = df['last_price']
        strikes = df['strike']
        dte_years = df['dte_hours'] / (365 * 24)  # Convert hours to years
        interest_rate = np.full(len(df), 0.06)  # 6% risk-free rate
        flags = df['opt_type'].str.lower().str[0]  # 'c' or 'p'

        # Compute IV vectorized
        ivs = py_vollib_vectorized.implied_volatility.vectorized_implied_volatility(
            price=option_prices,
            S=spot_prices,
            K=strikes,
            t=dte_years,
            r=interest_rate,
            flag=flags,
            model='black_scholes',
            on_error='ignore'  # Return NaN for invalid IVs
        )

        # Compute delta vectorized using computed IVs
        greeks = py_vollib_vectorized.get_all_greeks(
            flag=flags,
            S=spot_prices,
            K=strikes,
            t=dte_years,
            r=interest_rate,
            sigma=ivs,
            model='black_scholes',
            return_as='series'  # Return as pandas Series
        )
        deltas = greeks['delta']

        return ivs, deltas

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
        df['expiry_datetime'] = pd.to_datetime(df['expiry_date']) + pd.Timedelta(hours=15, minutes=30)
        now = pd.Timestamp.now()
        df['dte_hours'] = (df['expiry_datetime'] - now).dt.total_seconds() / 3600

        # -------- Step 6: IV and Delta Exposure --------
        df['iv'], df['delta'] = self.compute_iv_and_delta(df)
        df['delta_exposure'] = df['net_qty'] * df['delta']

        # -------- Step 7: Summary per Broker --------
        summary = {
            'timestamp': pd.Timestamp.now().isoformat(),
            'Broker': self.broker,
            'PE_Qty': int(df.loc[df['opt_type'] == 'PE', 'net_qty'].sum()),
            'CE_Qty': int(df.loc[df['opt_type'] == 'CE', 'net_qty'].sum()),
            'Premium': float(df['cur_amt'].sum()),
            'MTM': float(df['mtm'].sum()),
            'Pos_Delta': float(df['delta_exposure'].sum()),
            'Avg_IV': float(df['iv'].mean()) if not df['iv'].isna().all() else np.nan
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