
# Football games bot

## Overview

This is a python telegram bot made for chats inspired by [sds](https://www.youtube.com/@sds) games series it includes the following games
- Draft
- Guess the player
- would i lie to you (working progress)

## installation steps

if you wish to host this bot you need the following
- a public url, you can get a temporary one here [ngrok](https://ngrok.com/)
- bot token, you can get one from [bot father](https://web.telegram.org/k/#@BotFather)
- turso databse, either a hosted one or a dev server see details here[turso](https://turso.tech/)

have a .env file at the root directory with the following
``` env
  BOT_API_TOKEN = YOUR BOT TOEKN
  WEBHOOK_URL = YOUR PUBLIC URL FOR THE BOT      
  TURSO_DATABASE_URL = YOUR DB URL
  DEVELOPER_CHAT_ID = YOUR TELEGRAM ID IF YOU WNAT ERRORS SENT TO YOU
```
you need to have [pipenv](https://pipenv.pypa.io/en/latest/)
at the root directory do the following
``` bash
  pipenv shell
  pipenv install
```
if you provide a public url it well run with a webhook else it will run polling
to run the bot do the following, i will add a better way in the futrue
``` bash
  uvicorn main:app --host PUT A HOST HERE --port PUT A PORT HERE --reload
```
