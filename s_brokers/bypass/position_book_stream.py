import asyncio
import json
from collections import defaultdict
from common.config import get_redis_client_async
from datetime import datetime
from common.my_logger import logger
import logging

BROKER_KEYS = ["PE_Qty", "CE_Qty", "Premium", "MTM", "Margin_Used",
               "Delta_Skew_%", 'Gamma_to_Delta_%', "Pos_Gamma", "Pos_Delta", "sum_call_delta", "sum_put_delta"]
NUMERIC_KEYS = [ "PE_Qty", "CE_Qty", "Premium", "MTM", "Pos_Delta", "Pos_Gamma", "sum_call_delta", "sum_put_delta"]



logger.setLevel(logging.INFO)


class PositionBookStreamer:
    def __init__(self):
        self.redis = None

        self.last_written_ts_per_broker = defaultdict(lambda: 0)
        self.latest_data_per_broker = {}

        self.last_written_ts_consolidated = 0
        self.stream_gap = 5

        self.current_day = None

    async def start(self):
        logger.info("Starting position book streamer")
        self.redis = await get_redis_client_async()
        sub = self.redis.pubsub()
        await sub.subscribe("position_book_channel")

        async for msg in sub.listen():
            if msg["type"] != "message":
                continue

            try:
                await self.handle_message(msg["data"])
            except Exception as e:
                print(f"[Error] {e}")

    async def handle_message(self, raw_data):
        data = json.loads(raw_data)
        broker_key = data.get("Broker")
        timestamp = self._parse_iso_time(data["timestamp"])

        if broker_key is None or timestamp is None:
            return

        msg_day = datetime.fromtimestamp(timestamp).date()

        # Reset on new day
        if self.current_day is None:
            self.current_day = msg_day
        elif msg_day != self.current_day:
            logger.info(f"[Day Change Detected] Resetting state for new day: {msg_day}")
            self.latest_data_per_broker = {}
            self.last_written_ts_per_broker = defaultdict(lambda: 0)
            self.last_written_ts_consolidated = 0
            self.current_day = msg_day

        self.latest_data_per_broker[broker_key] = data

        # Broker-wise update
        last_written = self.last_written_ts_per_broker[broker_key]
        if timestamp - last_written >= self.stream_gap:
            await self._write_to_stream(data, tag=broker_key)
            self.last_written_ts_per_broker[broker_key] = timestamp

        # Consolidated update
        if timestamp - self.last_written_ts_consolidated >= self.stream_gap:
            consolidated = self._generate_consolidated_snapshot()
            await self._write_to_stream(consolidated, tag="ALL")
            self.last_written_ts_consolidated = timestamp

    def _generate_consolidated_snapshot(self):
        snapshot = {"timestamp": datetime.now().isoformat(), "Broker": "ALL", 'Delta_Skew_%':0.0}

        # Step 1: Accumulate numeric fields
        aggregates = {key: 0.0 for key in NUMERIC_KEYS}
        for broker_data in self.latest_data_per_broker.values():
            for key in NUMERIC_KEYS:
                try:
                    aggregates[key] += float(broker_data.get(key, 0))
                except (ValueError, TypeError):
                    pass

        # Step 2: Add raw aggregates to snapshot
        for key in NUMERIC_KEYS:
            snapshot[key] = round(aggregates[key], 4)

        # Step 3: Compute Delta Skew % and Gamma/Delta %
        try:
            total_delta_exp = aggregates['Pos_Delta']
            total_gamma_exp = aggregates['Pos_Gamma']
            call_delta = aggregates['sum_call_delta']
            put_delta = aggregates['sum_put_delta']

            if total_delta_exp != 0:
                delta_skew_pct = abs(call_delta - put_delta) / abs(total_delta_exp) * 100
                gamma_delta_pct = abs(total_gamma_exp / total_delta_exp) * 100
            else:
                delta_skew_pct = 0.0
                gamma_delta_pct = 0.0

            snapshot['Delta_Skew_%'] = round(delta_skew_pct, 2)
            snapshot['Gamma_to_Delta_%'] = round(gamma_delta_pct, 2)

        except Exception as e:
            logger.warning(f"[Consolidated Snapshot Error] {e}")

        return snapshot

    async def _write_to_stream(self, data, tag):
        stream_data = {k: str(data.get(k, "")) for k in BROKER_KEYS + ["timestamp", "Broker"]}

        if tag == "ALL":
            key = "position_book_stream:ALL"
        else:
            key = f"position_book_stream:{tag}"  # tag is broker name

        await self.redis.xadd(key, fields=stream_data)
        logger.debug(f"[Streamed] {tag} @ {data.get('timestamp')}")

    @staticmethod
    def _parse_iso_time(iso_str):
        try:
            dt = datetime.fromisoformat(iso_str)
            return int(dt.timestamp())
        except Exception:
            return None


if __name__ == "__main__":
    streamer = PositionBookStreamer()
    asyncio.run(streamer.start())
