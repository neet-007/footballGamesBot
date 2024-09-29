from asyncio import create_task
from contextlib import asynccontextmanager
from dotenv import load_dotenv
from os import getenv
from telegram import Update
from fastapi import FastAPI, Request, Response
from sys import exit
from bot.bot import ptb, sync_ptb
from custom_logging.setup_logging import setup_logging

load_dotenv()

BOT_API_TOKEN = getenv("BOT_API_TOKEN")

WEBHOOK_URL = getenv("WEBHOOK_URL")

if not BOT_API_TOKEN:
    print("Bot API token not found")
    exit(1)

app = FastAPI()

if not WEBHOOK_URL:
    setup_logging()
    print("Starting in polling mode")

    async def start_polling():
        if not sync_ptb.updater:
            exit(1)
        await sync_ptb.initialize()  
        await sync_ptb.start()       
        await sync_ptb.updater.start_polling()  
        
    create_task(start_polling())
else:
    @asynccontextmanager
    async def lifespan(_: FastAPI):
        print(f"Starting in webhook mode with URL: {WEBHOOK_URL}")
        await ptb.bot.setWebhook(WEBHOOK_URL)
        async with ptb:
            await ptb.start()
            yield
            await ptb.stop()

    setup_logging()
    app = FastAPI(lifespan=lifespan)

@app.post("/")
async def process_update(request: Request):
    req = await request.json()
    update = Update.de_json(req, ptb.bot)
    await ptb.process_update(update)
    return Response(status_code=200)

@app.get("/api/health")
def check_health():
     return {"status": "ok"}  

