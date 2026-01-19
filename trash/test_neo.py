import pyotp
from neo_api_client import NeoAPI

# 1. Initialize the client
# environment: 'prod' for live trading, 'uat' for testing
client = NeoAPI(
    consumer_key="9cd58e80-3b0f-409a-bc07-8ba6e8e4cc85",
    environment='prod'
)

try:
    # STEP 1: Initiate TOTP Login (Replaces the old .login() function)
    # You must provide your Mobile Number and UCC (Client Code)
    client.totp_login(
        mobile_number="+918448342040",
        ucc="S1VDU",
        totp= pyotp.TOTP("7DQLAD3SJ5Y5BAWHJI3SWIN7YQ").now()  # Enter current TOTP from app
    )

    # STEP 2: Validate with MPIN (This completes the 2FA process)
    # This step generates the 'Trade Token' needed to fix your error
    client.totp_validate(mpin="691025")


    # Now this will work without the 'Complete 2fa' error
    print("Account Limits:", client.limits())

except Exception as e:
    print(f"Login failed: {e}")

