"""Cliente de demostración. Uso: python demo.py   (con la API corriendo)"""
import asyncio
import os
import time

import httpx

URL = os.getenv("API_URL", "http://localhost:8000")


def titulo(t):
    print(f"\n{'=' * 64}\n{t}\n{'=' * 64}")


async def main():
    async with httpx.AsyncClient(base_url=URL, timeout=30) as c:
        await c.post("/reiniciar")

        titulo("1) SÍNCRONO: el cliente se queda esperando el cobro")
        t = time.perf_counter()
        r = await c.post("/comprar-sincrono/A1")
        print(f"   {r.status_code} {r.json()['estado']}  ->  tardó {time.perf_counter()-t:.2f} s")

        titulo("2) ASÍNCRONO: 202 inmediato + polling")
        t = time.perf_counter()
        r = await c.post("/comprar/A2")
        print(f"   {r.status_code} respuesta en {time.perf_counter()-t:.3f} s (¡no esperó al banco!)")
        id_compra = r.json()["id_compra"]
        while True:
            e = (await c.get(f"/compras/{id_compra}")).json()["estado"]
            print(f"   polling -> {e}  (t = {time.perf_counter()-t:.1f} s)")
            if e != "PROCESANDO_PAGO":
                break
            await asyncio.sleep(1)

        titulo("3) CONCURRENCIA: 5 clientes compran el MISMO asiento a la vez")
        rs = await asyncio.gather(*(c.post("/comprar/A3") for _ in range(5)))
        print("   códigos HTTP:", [r.status_code for r in rs], " (uno 202, el resto 409)")

        titulo("4) CONCURRENCIA: 5 compras de asientos distintos a la vez")
        t = time.perf_counter()
        rs = await asyncio.gather(*(c.post(f"/comprar/A{i}") for i in range(4, 9)))
        print(f"   códigos: {[r.status_code for r in rs]} en {time.perf_counter()-t:.3f} s")
        await asyncio.sleep(4)
        print("   asientos:", (await c.get("/asientos")).json()["asientos"])


asyncio.run(main())
