import requests
import json
from common.config import data_dir


def download_holidays():
    # Define the NSE API URL for trading holidays
    url = "https://www.nseindia.com/api/holiday-master?type=trading"

    # Define headers (User-Agent is essential to avoid blocking)
    headers = {'user-agent': 'Mozilla/5.0'}

    response = requests.get(url, headers=headers)

    # Check if the request was successful
    if response.status_code == 200:
        data = response.json()  # Parse JSON response
        holidays = [holiday["tradingDate"] for holiday in data.get("CM", [])]  # Extract dates only

        # Save to a JSON file
        with open(f"{data_dir}nse_holidays.json", "w") as f:
            json.dump(holidays, f, indent=4)

    else:
        print("Failed to fetch data:", response.status_code)


if __name__ == "__main__":
    download_holidays()

