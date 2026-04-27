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

The Dockerfile and railway.json force Railway to use Python, so it will not try to run `node`.

## Bot Commands

- `/start`
- `/help`
- `/id`
- `/account`

Admin commands:

- `/stats`
- `/addcredits USER_ID AMOUNT`
- `/ban USER_ID`
- `/unban USER_ID`
- `/broadcast message`
