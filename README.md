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

Send:

```text
/start
/ping
```

This version uses new database tables: `rza_users_v2`, `rza_referrals_v2`, `rza_bot_logs_v2` to avoid old table conflicts.
