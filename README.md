# Materias Unicaba Bot Telegram

Mi nombre es Boris Sebastián Salinas.

Este es un proyecto personal hecho para consultar horarios de cursada a través de un bot de Telegram de una forma más cómoda.

La idea surgió de una necesidad mía: revisar los horarios manualmente en la cartelera me parecía incómodo e ineficiente, así que armé este bot para tener esa información más a mano y con menos pasos.

## Qué hace

El bot consulta hojas publicadas de Google Sheets, busca materias por código y responde por Telegram con el aula y el horario correspondiente.

Comandos disponibles:

- `/start`
- `/hoy`
- `/semana`
- `/aula CODIGO`

## Personalización

Si alguien quiere usarlo de forma personal, tiene que adaptar dos cosas:

1. Crear un archivo `.env` con su token de Telegram.
2. Cambiar los códigos de asignatura en `MIS_CODIGOS` dentro de `materias.py` por los que quiera consultar.

Ejemplo de `.env`:

```env
TELEGRAM_TOKEN=tu_token_de_telegram
```

## Cómo usarlo localmente

Instalar dependencias:

```bash
pip install -r requirements.txt
```

Ejecutar:

```bash
python materias.py
```

## Deploy

El proyecto también puede desplegarse en Render usando las variables de entorno:

- `TELEGRAM_TOKEN`
- `WEBHOOK_URL`

## Nota

Este proyecto está pensado principalmente para uso personal. Si otra persona quiere reutilizarlo, probablemente tenga que ajustar links, códigos de materias y configuración del bot para que la experiencia sea realmente propia.

Las materias y el link actual están pensados para la UniCABA (Universidad de la Ciudad de Buenos Aires).
