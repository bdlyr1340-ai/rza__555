# RZA Telegram Bot - Railway Ready

## Railway Variables

```env
BOT_TOKEN=
DATABASE_URL=
ADMIN_IDS=
DEFAULT_CREDITS=3
REFERRAL_BONUS=5
LOG_LEVEL=INFO
```

## Start Command

```bash
python main.py
```

## Test

Send to the bot:

```text
/start
/ping
```

If the deployment is active but the bot does not answer, stop/delete any other Railway service using the same BOT_TOKEN, then redeploy this project.
