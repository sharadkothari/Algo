from fastapi import FastAPI
import psutil
import platform
import datetime as dt
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or restrict to dashboard's IP
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/stats")
def get_stats():
    battery=psutil.sensors_battery()
    if battery is not None:
        plugged = '⚡' if battery.power_plugged else ''
        battery_stat = [f'{battery.percent:.0f}% {plugged}']
    else:
        battery_stat = ["NA"]
    return {
        "hostname": platform.node(),
        "cpu": psutil.cpu_percent(interval=1),
        "memory": psutil.virtual_memory().percent,
        "disk": psutil.disk_usage('/').percent,
        "battery": battery_stat,
        "time": dt.datetime.now().strftime("%H:%M:%S")
    }

if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000, access_log=False)