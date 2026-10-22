import asyncio
import os
import uuid
from datetime import datetime

from pathlib import Path
import time

from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

app = FastAPI(title="API Preventa de Boletos - Cine")

ESTATICOS = Path(__file__).parent / "static"
app.mount("/static", StaticFiles(directory=ESTATICOS), name="static")  # css/ y js/

# Se configuran por variables de entorno (ver docker-compose.yml) para poder
# demostrar el caso exitoso y el caso de timeout sin tocar el código.
PAGO_SEGUNDOS = float(os.getenv("PAGO_SEGUNDOS", "3"))        # lo que tarda el "banco"
TIMEOUT_SEGUNDOS = float(os.getenv("TIMEOUT_SEGUNDOS", "10"))  # paciencia máxima

# "Base de datos" en memoria. True = libre, False = ocupado / reservado
asientos = {f"A{i}": True for i in range(1, 11)}
compras = {}  # {id_compra: {asiento, estado, creado_en}}
INICIO = {}   # id_compra -> time.monotonic() (para mostrar el avance en la pantalla)


def log(msg: str):
    print(f"[{datetime.now():%H:%M:%S.%f}"[:-3] + f"] {msg}", flush=True)


async def llamar_al_banco():
    """Simula la pasarela de pagos: una espera NO bloqueante (no congela el servidor)."""
    await asyncio.sleep(PAGO_SEGUNDOS)


# ----------------------------------------------------------------------
# TAREA EN SEGUNDO PLANO
# ----------------------------------------------------------------------
async def procesar_pago(id_compra: str, asiento_id: str):
    log(f"💳 {id_compra[:8]} · cobrando asiento {asiento_id}...")
    try:
        # wait_for corta la espera si el banco supera el timeout
        await asyncio.wait_for(llamar_al_banco(), timeout=TIMEOUT_SEGUNDOS)
        compras[id_compra]["estado"] = "COMPLETADO"      # el asiento ya está reservado
        log(f"✅ {id_compra[:8]} · compra completada ({asiento_id})")
    except asyncio.TimeoutError:
        asientos[asiento_id] = True                       # liberar para otros usuarios
        compras[id_compra]["estado"] = "CANCELADO_TIMEOUT"
        log(f"⏱️  {id_compra[:8]} · TIMEOUT, asiento {asiento_id} liberado")
    except Exception:
        asientos[asiento_id] = True
        compras[id_compra]["estado"] = "ERROR_PAGO"
        log(f"❌ {id_compra[:8]} · error de pago, asiento {asiento_id} liberado")


def reservar(asiento_id: str) -> str:
    """Valida y bloquea el asiento. No hay 'await' entre el chequeo y la
    reserva, así que el event loop no puede intercalar a otro cliente."""
    if asiento_id not in asientos:
        raise HTTPException(404, "El asiento no existe")
    if not asientos[asiento_id]:
        raise HTTPException(409, "El asiento ya está ocupado")
    asientos[asiento_id] = False
    id_compra = str(uuid.uuid4())
    compras[id_compra] = {
        "asiento": asiento_id,
        "estado": "PROCESANDO_PAGO",
        "creado_en": datetime.now().isoformat(),
    }
    INICIO[id_compra] = time.monotonic()
    return id_compra


# ----------------------------------------------------------------------
@app.get("/asientos")
async def consultar_asientos():
    return {"asientos": asientos}


# ASÍNCRONO: responde 202 al instante y cobra en segundo plano
@app.post("/comprar/{asiento_id}", status_code=202)
async def iniciar_compra(asiento_id: str, bg: BackgroundTasks):
    id_compra = reservar(asiento_id)
    bg.add_task(procesar_pago, id_compra, asiento_id)
    return {
        "mensaje": "Solicitud recibida. Procesando pago en segundo plano...",
        "id_compra": id_compra,
        "asiento": asiento_id,
        "consulta_estado": f"/compras/{id_compra}",
    }


# SÍNCRONO (solo para comparar): el cliente espera todo el cobro
@app.post("/comprar-sincrono/{asiento_id}")
async def comprar_sincrono(asiento_id: str):
    id_compra = reservar(asiento_id)
    await procesar_pago(id_compra, asiento_id)
    return {"id_compra": id_compra, "estado": compras[id_compra]["estado"]}


# POLLING: el cliente pregunta cómo va su compra
@app.get("/compras/{id_compra}")
async def consultar_estado_compra(id_compra: str):
    compra = compras.get(id_compra)
    if not compra:
        raise HTTPException(404, "Transacción no encontrada")
    return {"id_compra": id_compra, **compra}


# Utilidad para repetir la demo
@app.post("/reiniciar")
async def reiniciar():
    for k in asientos:
        asientos[k] = True
    compras.clear()
    INICIO.clear()
    return {"mensaje": "Estado reiniciado"}


# ----------------------------------------------------------------------
# PANTALLA VISUAL  (http://localhost:8000/)
# ----------------------------------------------------------------------
class Config(BaseModel):
    pago_segundos: float
    timeout_segundos: float


@app.get("/", include_in_schema=False)
async def pantalla():
    return FileResponse(ESTATICOS / "index.html")


@app.get("/estado", include_in_schema=False)
async def estado():
    """Foto completa del sistema para que la pantalla se dibuje."""
    ahora = time.monotonic()
    vista = {}
    for a, libre in asientos.items():
        vista[a] = "libre"
        if not libre:
            vista[a] = "reservado"
            for c in compras.values():
                if c["asiento"] == a and c["estado"] == "COMPLETADO":
                    vista[a] = "ocupado"
    lista = [
        {"id": i, **c, "transcurrido": round(ahora - INICIO.get(i, ahora), 2)}
        for i, c in compras.items()
    ]
    return {
        "asientos": vista,
        "compras": lista[-8:][::-1],
        "config": {"pago": PAGO_SEGUNDOS, "timeout": TIMEOUT_SEGUNDOS},
    }


@app.post("/config", include_in_schema=False)
async def configurar(cfg: Config):
    global PAGO_SEGUNDOS, TIMEOUT_SEGUNDOS
    PAGO_SEGUNDOS, TIMEOUT_SEGUNDOS = cfg.pago_segundos, cfg.timeout_segundos
    return {"pago": PAGO_SEGUNDOS, "timeout": TIMEOUT_SEGUNDOS}
