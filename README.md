# RZA Telegram Bot - Railway Ready

## Railway variables

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

Send:

```text
/start
/ping
```

The bot deletes any old Telegram webhook before polling. This fixes the common issue where Railway is running but Telegram messages do not reach the bot.
