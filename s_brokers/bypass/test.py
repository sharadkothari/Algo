import asyncio
from Kite import Kite


async def main():
    kite = await Kite.create("ym3006", {})
    print(await kite.position_book())


if __name__ == "__main__":
    asyncio.run(main())
