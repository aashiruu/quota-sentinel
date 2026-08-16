import asyncio
import time
import httpx


async def run_noisy_tenant(client: httpx.AsyncClient, duration_seconds: int = 15):
    start = time.time()
    success, throttled = 0, 0
    while time.time() - start < duration_seconds:
        res = await client.get("/api/v1/data", headers={"X-Tenant-ID": "tenant-noisy"})
        if res.status_code == 200:
            success += 1
        elif res.status_code == 429:
            throttled += 1
        await asyncio.sleep(0.02)
    return {"tenant": "tenant-noisy", "success": success, "throttled": throttled}


async def run_steady_standard_tenant(client: httpx.AsyncClient, duration_seconds: int = 15):
    start = time.time()
    success, throttled = 0, 0
    while time.time() - start < duration_seconds:
        res = await client.get("/api/v1/data", headers={"X-Tenant-ID": "tenant-standard"})
        if res.status_code == 200:
            success += 1
        elif res.status_code == 429:
            throttled += 1
        await asyncio.sleep(3.0)  # ~5 req in 15s (well under limit 20)
    return {"tenant": "tenant-standard", "success": success, "throttled": throttled}


async def run_steady_free_tenant(client: httpx.AsyncClient, duration_seconds: int = 15):
    start = time.time()
    success, throttled = 0, 0
    while time.time() - start < duration_seconds:
        res = await client.get("/api/v1/data", headers={"X-Tenant-ID": "tenant-free"})
        if res.status_code == 200:
            success += 1
        elif res.status_code == 429:
            throttled += 1
        await asyncio.sleep(4.0)  # ~3 req in 15s (under limit 5)
    return {"tenant": "tenant-free", "success": success, "throttled": throttled}


async def main():
    async with httpx.AsyncClient(base_url="http://localhost:8000") as client:
        print("Starting Noisy-Neighbor Simulation (15s concurrent execution)...")
        results = await asyncio.gather(
            run_noisy_tenant(client, 15),
            run_noisy_tenant(client, 15),  # Second noisy worker
            run_steady_standard_tenant(client, 15),
            run_steady_free_tenant(client, 15),
        )

        print("\n=== Simulation Results ===")
        for r in results:
            print(f"Tenant: {r['tenant']} | 200 OK: {r['success']} | 429 Throttled: {r['throttled']}")


if __name__ == "__main__":
    asyncio.run(main())
