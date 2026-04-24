# Telegram Bot Railway Fixed V2

## Railway Variables

Required:

```env
BOT_TOKEN=YOUR_TELEGRAM_BOT_TOKEN
FRIDA_AGENTS={"phone1":"http://YOUR_AGENT_IP:5000"}
```

Database:
- Add PostgreSQL service in Railway.
- In your bot service > Variables, add Reference Variable for DATABASE_URL from the PostgreSQL service.
- Or expose PGHOST, PGPORT, PGUSER, PGPASSWORD, PGDATABASE to the bot service.

## Test

Open Telegram and send:

```text
/start
/debug
```

If database is not connected, the menu will still open. The debug button/message will show the exact problem.
