import  py_vollib_vectorized
import numpy as np
import pandas as pd

def compute_deltas(candles, spot, expiry_days, option_type_hint=None):
    """Compute delta for each option using py_vollib_vectorized.get_all_greeks."""
    results = {}

    prices = []
    spots = []
    strikes = []
    times = []
    rates = []
    implied_vols = []
    option_types = []
    keys = []

    for key, candle in candles.items():
        try:
            df = pd.DataFrame(candle).T.reset_index()
            price = float(candle["close"])
            strike = float(candle["strike"])
            option_type = "c" if key.endswith("CE") else "p"

            # Assume IV = 0.2 for now (can later be calculated)
            iv = 0.20

            prices.append(price)
            spots.append(spot)
            strikes.append(strike)
            times.append(expiry_days / 365.0)
            rates.append(0.06)
            implied_vols.append(iv)
            option_types.append(option_type)
            keys.append(key)
        except Exception as e:
            print(f"Skipping {key} due to error: {e}")
            continue

    if not keys:
        return results

    # Convert to NumPy arrays
    prices = np.array(prices)
    spots = np.array(spots)
    strikes = np.array(strikes)
    times = np.array(times)
    rates = np.array(rates)
    implied_vols = np.array(implied_vols)
    option_types = np.array(option_types)

    # Compute all Greeks
    greeks = py_vollib_vectorized.get_all_greeks(
        price=prices,
        S=spots,
        K=strikes,
        t=times,
        r=rates,
        sigma=implied_vols,
        flag=option_types
    )

    # Populate results
    for i, key in enumerate(keys):
        results[key] = {
            "strike": strikes[i],
            "delta": greeks["delta"][i],
            "option_type": option_types[i],
            "ltp": prices[i],
        }

    return results
