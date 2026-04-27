# RZA Telegram Bot - Railway Ready

## Railway Variables

Required:

```env
BOT_TOKEN=
DATABASE_URL=
```

Optional:

```env
ADMIN_IDS=
DEFAULT_CREDITS=3
REFERRAL_BONUS=5
LOG_LEVEL=INFO
```

## Start Command

```bash
python main.py
```

## Commands

- `/start`
- `/help`
- `/id`
- `/account`
- `/me`
- `/ref`

Admin:

- `/stats`
- `/addcredits USER_ID AMOUNT`
- `/ban USER_ID`
- `/unban USER_ID`
- `/broadcast message`

Railway will build with the Dockerfile, so it will not run `node`.
The database file is named `rza_database.py` to avoid conflicts with any folder named `db`.
