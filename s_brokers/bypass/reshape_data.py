import pandas as pd
import py_vollib_vectorized
import numpy as np
import json
from common.my_logger import logger

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

        return ivs, greeks

    def position_book(self, df):
        try:
            # -------- Step 1: Add Tick Data --------
            df['symbol_key'] = df['exch'] + ':' + df['symbol']
            df[self.tick_columns] = df['symbol_key'].apply(self.extract_tick_fields)
            df = df[df['opt_type'].isin(['CE', 'PE'])].copy()

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
            df['iv'], greeks = self.compute_iv_and_delta(df)
            df['delta'] = greeks['delta']
            df['gamma'] = greeks['gamma']
            df['theta'] = greeks['theta']
            df['delta_exposure'] = df['net_qty'] * df['delta']
            df['gamma_exposure'] = df['net_qty'] * df['gamma']
            df['theta_exposure'] = df['net_qty'] * df['theta']

            # -------- Step 7: Call/Put Delta Split for Skew --------
            call_delta = df.loc[df['opt_type'] == 'CE', 'delta_exposure'].sum()
            put_delta = df.loc[df['opt_type'] == 'PE', 'delta_exposure'].sum()
            call_delta_abs = abs(call_delta)
            put_delta_abs = abs(put_delta)
            numerator = abs(call_delta_abs - put_delta_abs)
            denominator = call_delta_abs + put_delta_abs
            delta_skew_ratio = numerator / denominator * 100 if denominator != 0 else 0

            # -------- Step 8: Gamma-to-Delta Ratio --------
            total_delta_exp = df['delta_exposure'].sum()
            total_delta_exp = df['delta_exposure'].sum()
            total_gamma_exp = df['gamma_exposure'].sum()
            gamma_delta_ratio = abs(total_gamma_exp / total_delta_exp) * 100 if total_delta_exp != 0 else 0

            # -------- Step 9: Theta-to-Delta Ratio  --------
            total_theta_exp = df['theta_exposure'].sum()
            theta_delta_ratio = abs(total_theta_exp / total_delta_exp) * 100 if total_delta_exp != 0 else 0

            # -------- Step 10: Summary per Broker --------
            summary = {
                'timestamp': pd.Timestamp.now().isoformat(),
                'Broker': self.broker,
                'PE_Qty': int(df.loc[df['opt_type'] == 'PE', 'net_qty'].sum()),
                'CE_Qty': int(df.loc[df['opt_type'] == 'CE', 'net_qty'].sum()),
                'Premium': float(df['cur_amt'].sum()),
                'MTM': float(df['mtm'].sum()),
                'Pos_Delta': float(total_delta_exp),
                'Avg_IV': float(df['iv'].mean()) if not df['iv'].isna().all() else None,
                'Pos_Gamma': float(total_gamma_exp),
                'Pos_Theta': float(total_theta_exp),
                'Gamma_to_Delta_%': round(gamma_delta_ratio, 2),
                'Theta_to_Delta_%': round(theta_delta_ratio, 2),
                'Delta_Skew_%': round(delta_skew_ratio, 2),
                'sum_call_delta': float(call_delta),
                'sum_put_delta': float(put_delta),
            }
            return summary

        except Exception as e:
            logger.warning(f"[Position Book Error] for {self.broker} | {e}")
            import traceback;
            traceback.print_exc()
            return {}

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