import pandas as pd
import numpy as np
from expiry_helper import Expiry  # Assumed to provide expiry date
from option_greeks import compute_option_delta  # Assume py_vollib or similar backend

# -------- Step 0: Setup (assumes this per broker) --------
df = ...  # Broker position DataFrame
ticks = ...  # {'SENSEX2560374000PE': 12.5, ...} — includes spot price too

underlying_symbol = 'SENSEX'  # Modify per segment if needed
spot_price = ticks.get(underlying_symbol, np.nan)

expiry_obj = Expiry()  # Your helper to get expiry from symbol
risk_free_rate = 0.06
iv = 0.18  # Placeholder — use computed or fixed per symbol

# -------- Step 1: Add LTP --------
df['ltp'] = df['symbol'].map(ticks)

# -------- Step 2: Net Qty and Current Amount --------
df['net_qty'] = df['sell_qty'] - df['buy_qty']
df['cur_amt'] = df['net_qty'] * df['ltp']

# -------- Step 3: Net Premium --------
df['net_amt'] = df['sell_amt'] - df['buy_amt']

# -------- Step 4: MTM --------
df['mtm'] = df['cur_amt'] + df['net_amt']

# -------- Step 5: Extract Option Type --------
df['option_type'] = df['symbol'].str[-2:]

# -------- Step 6: Extract Strike --------
# Assumes strike is last 8 digits before option type
df['strike'] = df['symbol'].str.extract(r'(\d{8})(?=..$)').astype(float)

# -------- Step 7: Add Expiry --------
df['expiry'] = df['symbol'].map(lambda x: expiry_obj.get_expiry(x))


# Time to expiry in **fraction of a year** (hours converted)
expiry_datetime = df['expiry'] + pd.Timedelta(hours=15, minutes=30)  # Expiry ends at 15:30
now = pd.Timestamp.now()
df['dte_hours'] = (expiry_datetime - now).dt.total_seconds() / 3600

# -------- Step 9: Compute Delta --------
def safe_compute_delta(row):
    try:
        return compute_option_delta(
            S=spot_price,
            K=row['strike'],
            t=row['dte_hours'] / (365 * 24),  # dte in hours, convert to years
            r=risk_free_rate,
            sigma=iv,
            flag=row['option_type'].lower()
        )
    except Exception:
        return np.nan

df['delta'] = df.apply(safe_compute_delta, axis=1)

# -------- Step 10: Delta Exposure --------
df['delta_exposure'] = df['net_qty'] * df['delta']

# -------- Step 11: Summary per Broker --------
summary = {
    'broker': 'Zerodha',  # Inject actual broker ID here
    'PE_Qty': df.loc[df['option_type'] == 'PE', 'net_qty'].sum(),
    'CE_Qty': df.loc[df['option_type'] == 'CE', 'net_qty'].sum(),
    'Premium': df['cur_amt'].sum(),
    'MTM': df['mtm'].sum(),
    'Pos_Delta': df['delta_exposure'].sum()
}
