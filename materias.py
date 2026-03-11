import asyncio
import datetime
import os
import unicodedata

import pandas as pd
from dotenv import load_dotenv
from telegram import Update
from telegram.ext import ApplicationBuilder, CommandHandler, ContextTypes


load_dotenv()
TOKEN = os.getenv("TELEGRAM_TOKEN")
WEBHOOK_BASE_URL = os.getenv("WEBHOOK_URL", "").rstrip("/")
PORT = int(os.getenv("PORT", "10000"))
WEBHOOK_PATH = "/telegram"
HEALTHCHECK_PATH = "/healthcheck"

if not TOKEN:
    raise ValueError("TELEGRAM_TOKEN no esta definido en el .env")

LINKS = {
    "Lunes": "https://docs.google.com/spreadsheets/d/e/2PACX-1vSc_T_BQjbn3uPelioCgx52UM5Py-qNhJN0TYPd1kmsN5jdb3Q8rAaIvNMF_2ZTzQt6bH--yIWQKrKR/pub?gid=1915752353&single=true&output=csv",
    "Martes": "https://docs.google.com/spreadsheets/d/e/2PACX-1vSc_T_BQjbn3uPelioCgx52UM5Py-qNhJN0TYPd1kmsN5jdb3Q8rAaIvNMF_2ZTzQt6bH--yIWQKrKR/pub?gid=466778263&single=true&output=csv",
    "Miercoles": "https://docs.google.com/spreadsheets/d/e/2PACX-1vSc_T_BQjbn3uPelioCgx52UM5Py-qNhJN0TYPd1kmsN5jdb3Q8rAaIvNMF_2ZTzQt6bH--yIWQKrKR/pub?gid=615483345&single=true&output=csv",
    "Jueves": "https://docs.google.com/spreadsheets/d/e/2PACX-1vSc_T_BQjbn3uPelioCgx52UM5Py-qNhJN0TYPd1kmsN5jdb3Q8rAaIvNMF_2ZTzQt6bH--yIWQKrKR/pub?gid=682416571&single=true&output=csv",
}

MIS_CODIGOS = {
    "Lunes": "ASIG00126",
    "Martes": "ASIG00131",
    "Miercoles": "ASIG00122",
    "Jueves": "ASIG00124",
}

DATA_CACHE = {}


class HorariosError(Exception):
    """Error controlado al leer o interpretar los horarios."""


def normalizar_texto(valor):
    if valor is None:
        return ""

    texto = str(valor).strip()
    texto = unicodedata.normalize("NFKD", texto)
    texto = "".join(char for char in texto if not unicodedata.combining(char))
    return " ".join(texto.lower().split())


def resolver_columna(df, candidatos):
    columnas_normalizadas = {
        normalizar_texto(columna): columna for columna in df.columns
    }

    for candidato in candidatos:
        columna = columnas_normalizadas.get(normalizar_texto(candidato))
        if columna:
            return columna

    raise HorariosError(
        f"No encontre ninguna de estas columnas: {', '.join(candidatos)}"
    )


def detectar_fila_encabezado(df_raw):
    candidatos_objetivo = ["codigo", "asignatura", "materia", "aula", "horario"]

    for indice, fila in df_raw.iterrows():
        valores = [normalizar_texto(valor) for valor in fila.tolist()]

        if "codigo" in valores and "aula" in valores and "horario" in valores:
            return indice

        coincidencias = sum(1 for valor in valores if valor in candidatos_objetivo)
        if coincidencias >= 3:
            return indice

    raise HorariosError("No pude detectar la fila de encabezados en la hoja.")


def cargar_dia(dia):
    if dia not in DATA_CACHE:
        try:
            df_raw = pd.read_csv(LINKS[dia], header=None)
        except Exception as exc:
            raise HorariosError(
                f"No pude leer la hoja de {dia}. Verifica que el Google Sheet este publicado como CSV."
            ) from exc

        if df_raw.empty:
            raise HorariosError(f"La hoja de {dia} esta vacia.")

        fila_encabezado = detectar_fila_encabezado(df_raw)
        encabezados = df_raw.iloc[fila_encabezado].fillna("")
        df = df_raw.iloc[fila_encabezado + 1 :].copy()
        df.columns = encabezados
        df = df.dropna(how="all")

        columnas = {
            "codigo": resolver_columna(
                df, ["Codigo", "Codigo Materia", "Cod", "ID", "Comision"]
            ),
            "materia": resolver_columna(
                df, ["Asignatura", "Materia", "Nombre", "Catedra"]
            ),
            "aula": resolver_columna(df, ["Aula", "Salon", "Sala"]),
            "horario": resolver_columna(df, ["Horario", "Hora", "Franja", "Turno"]),
        }

        DATA_CACHE[dia] = {
            "df": df.fillna(""),
            "columnas": columnas,
        }

    return DATA_CACHE[dia]


def buscar_codigo(codigo, dia):
    data_dia = cargar_dia(dia)
    df = data_dia["df"]
    columnas = data_dia["columnas"]

    codigo_buscado = normalizar_texto(codigo)
    serie_codigos = df[columnas["codigo"]].astype(str).map(normalizar_texto)
    fila = df[serie_codigos.str.contains(codigo_buscado, na=False)]

    if fila.empty:
        return None

    fila = fila.iloc[0]

    return {
        "materia": str(fila[columnas["materia"]]).strip(),
        "aula": str(fila[columnas["aula"]]).strip(),
        "horario": str(fila[columnas["horario"]]).strip(),
    }


def formatear_respuesta(dia, data):
    return (
        f"{dia}\n\n"
        f"{data['materia']}\n"
        f"Aula: {data['aula']}\n"
        f"Horario: {data['horario']}"
    )


def obtener_dia_actual():
    dias = {
        0: "Lunes",
        1: "Martes",
        2: "Miercoles",
        3: "Jueves",
    }
    return dias.get(datetime.datetime.today().weekday())


async def responder(update: Update, mensaje):
    if update.message:
        await update.message.reply_text(mensaje)


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await responder(
        update,
        "Bot de aulas\n\n"
        "/hoy\n"
        "/semana\n"
        "/aula CODIGO",
    )


async def hoy(update: Update, context: ContextTypes.DEFAULT_TYPE):
    dia = obtener_dia_actual()

    if dia not in LINKS:
        await responder(update, "Hoy no tenes cursada.")
        return

    try:
        codigo = MIS_CODIGOS[dia]
        data = buscar_codigo(codigo, dia)
    except HorariosError as exc:
        await responder(update, str(exc))
        return

    if not data:
        await responder(update, f"No encontre el aula para {codigo} en {dia}.")
        return

    await responder(update, formatear_respuesta(dia, data))


async def semana(update: Update, context: ContextTypes.DEFAULT_TYPE):
    respuesta = []

    for dia in LINKS:
        try:
            codigo = MIS_CODIGOS[dia]
            data = buscar_codigo(codigo, dia)
        except HorariosError as exc:
            respuesta.append(f"{dia}\n\nError: {exc}")
            continue

        if data:
            respuesta.append(formatear_respuesta(dia, data))

    if not respuesta:
        await responder(update, "No encontre horarios en ninguna hoja.")
        return

    await responder(update, "\n\n".join(respuesta))


async def aula(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not context.args:
        await responder(update, "Usa /aula CODIGO")
        return

    codigo = context.args[0]

    for dia in LINKS:
        try:
            data = buscar_codigo(codigo, dia)
        except HorariosError:
            continue

        if data:
            await responder(update, formatear_respuesta(dia, data))
            return

    await responder(update, "No encontre ese codigo.")


def crear_aplicacion(updater_activo):
    builder = ApplicationBuilder().token(TOKEN)

    if not updater_activo:
        builder = builder.updater(None)

    application = builder.build()
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("hoy", hoy))
    application.add_handler(CommandHandler("semana", semana))
    application.add_handler(CommandHandler("aula", aula))

    return application


async def ejecutar_webhook():
    import uvicorn
    from starlette.applications import Starlette
    from starlette.requests import Request
    from starlette.responses import PlainTextResponse, Response
    from starlette.routing import Route

    if not WEBHOOK_BASE_URL:
        raise ValueError(
            "WEBHOOK_URL no esta definido. En Render configuralo con la URL publica del servicio, por ejemplo https://tu-bot.onrender.com"
        )

    application = crear_aplicacion(updater_activo=False)
    webhook_url = f"{WEBHOOK_BASE_URL}{WEBHOOK_PATH}"

    async def telegram_webhook(request: Request) -> Response:
        await application.update_queue.put(
            Update.de_json(data=await request.json(), bot=application.bot)
        )
        return Response(status_code=200)

    async def healthcheck(_: Request) -> PlainTextResponse:
        return PlainTextResponse("ok")

    web_app = Starlette(
        routes=[
            Route("/", healthcheck, methods=["GET"]),
            Route(HEALTHCHECK_PATH, healthcheck, methods=["GET"]),
            Route(WEBHOOK_PATH, telegram_webhook, methods=["POST"]),
        ]
    )

    webserver = uvicorn.Server(
        uvicorn.Config(
            app=web_app,
            host="0.0.0.0",
            port=PORT,
            use_colors=False,
        )
    )

    async with application:
        await application.start()
        await application.bot.set_webhook(
            url=webhook_url,
            allowed_updates=Update.ALL_TYPES,
            drop_pending_updates=True,
        )
        try:
            await webserver.serve()
        finally:
            await application.bot.delete_webhook()
            await application.stop()


def main():
    if WEBHOOK_BASE_URL or os.getenv("RENDER"):
        asyncio.run(ejecutar_webhook())
        return

    application = crear_aplicacion(updater_activo=True)
    application.run_polling(drop_pending_updates=True)


if __name__ == "__main__":
    main()
