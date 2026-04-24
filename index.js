import 'dotenv/config';
import express from 'express';
import pg from 'pg';
import { Telegraf, Markup, session } from 'telegraf';

const { Pool } = pg;

/*
  ============================================================
  مساعد الدفع - Telegram Payment Assistant
  عدّل هذا القسم فقط مستقبلاً: النصوص، طرق الدفع، الروابط، التعليمات
  ============================================================
*/
const APP_CONFIG = {
  projectName: {
    ar: 'مساعد الدفع',
    en: 'Payment Assistant'
  },

  siteUrl: process.env.SITE_URL || 'https://gpt.aide.freespaces.app/',
  supportUrl: process.env.SUPPORT_URL || 'https://t.me/t4i44s',
  defaultLanguage: 'ar',

  // طرق الدفع: عدّل العناوين والتفاصيل من هنا فقط
  paymentMethods: [
    {
      id: 'binance_pay',
      title: { ar: 'Binance Pay', en: 'Binance Pay' },
      details: {
        ar: `💳 طريقة الدفع: Binance Pay\n\nاكتب هنا Binance Pay ID أو رابط الدفع الخاص بيك.\n\n⚠️ مهم جداً:\nبعد الدفع لازم ترسل:\n1) رمز التحويل\n2) رمز الملاحظة / Note / Memo\nحتى يتم التحقق من طلبك بسرعة.`,
        en: `💳 Payment method: Binance Pay\n\nPut your Binance Pay ID or payment link here.\n\n⚠️ Important:\nAfter payment, send:\n1) Transfer code\n2) Note / Memo code\nso your order can be verified quickly.`
      }
    },
    {
      id: 'usdt_trc20',
      title: { ar: 'USDT TRC20', en: 'USDT TRC20' },
      details: {
        ar: `💳 طريقة الدفع: USDT TRC20\n\nاكتب هنا عنوان محفظة TRC20 الخاص بيك.\n\n⚠️ مهم جداً:\nأرسل رمز التحويل ورمز الملاحظة بعد الدفع.`,
        en: `💳 Payment method: USDT TRC20\n\nPut your TRC20 wallet address here.\n\n⚠️ Important:\nSend transfer code and memo/note after payment.`
      }
    },
    {
      id: 'custom',
      title: { ar: 'طريقة دفع أخرى', en: 'Other payment method' },
      details: {
        ar: `💳 طريقة دفع أخرى\n\nراسل الدعم حتى يعطيك تفاصيل الدفع المناسبة.\nبعدها ارجع للبوت وارسل رمز التحويل ورمز الملاحظة.`,
        en: `💳 Other payment method\n\nContact support to receive payment details.\nThen return to the bot and send transfer code and memo/note.`
      }
    }
  ],

  texts: {
    ar: {
      chooseLang: 'اختر اللغة / Choose language',
      savedLang: 'تم حفظ اللغة ✅',
      start: 'هلا بيك 👋\nهذا بوت مساعد الدفع.\nنفس فكرة الموقع: ترسل السيشن، بعدها تختار طريقة الدفع، وبعد الدفع ترسل رمز التحويل ورمز الملاحظة.',
      mainMenu: 'اختار من الأزرار:',
      sendSession: 'إرسال السيشن',
      openSite: 'فتح الموقع',
      language: 'اللغة',
      support: 'الدعم',
      myOrders: 'طلباتي',
      profile: 'حسابي',
      back: 'رجوع',
      cancel: 'إلغاء',
      sessionPrompt: 'ارسل السيشن الآن برسالة واحدة.\n\nمثال: الصق Session / Token / Cookies / البيانات المطلوبة مثل ما يطلبها الموقع.\n\n⚠️ لا ترسل أكثر من رسالة، اجمعها برسالة واحدة.',
      sessionSaved: 'تم استلام السيشن ✅\nهسه اختار طريقة الدفع:',
      paymentPrompt: 'اختر طريقة الدفع:',
      sendPaymentProof: 'بعد ما تدفع، ارسل الآن رمز التحويل + رمز الملاحظة / Memo / Note.\n\nمثال:\nTransfer: 123ABC\nMemo: 7788\nNotes: دفعت وتم التحويل',
      orderCreated: 'تم إرسال طلبك للإدارة بنجاح ✅\nرقم الطلب:',
      noOrders: 'ما عندك طلبات بعد.',
      canceled: 'تم الإلغاء ✅',
      unknown: 'ما فهمت عليك. استخدم الأزرار أو اكتب /start',
      adminOnly: 'هذا الأمر للإدارة فقط.',
      howItWorks: 'طريقة الاستخدام:\n1) اضغط إرسال السيشن.\n2) الصق السيشن برسالة واحدة.\n3) اختار طريقة الدفع.\n4) بعد الدفع ارسل رمز التحويل ورمز الملاحظة.\n5) الإدارة تراجع الطلب وتقبله.'
    },
    en: {
      chooseLang: 'Choose language / اختر اللغة',
      savedLang: 'Language saved ✅',
      start: 'Welcome 👋\nThis is the Payment Assistant bot.\nLike the website: send your session, choose a payment method, then send transfer code and memo/note after payment.',
      mainMenu: 'Choose from the buttons:',
      sendSession: 'Send session',
      openSite: 'Open site',
      language: 'Language',
      support: 'Support',
      myOrders: 'My orders',
      profile: 'My profile',
      back: 'Back',
      cancel: 'Cancel',
      sessionPrompt: 'Send your session now in one message.\n\nExample: paste Session / Token / Cookies / required data exactly like the website asks.\n\n⚠️ Do not send multiple messages. Put everything in one message.',
      sessionSaved: 'Session received ✅\nNow choose a payment method:',
      paymentPrompt: 'Choose payment method:',
      sendPaymentProof: 'After paying, send transfer code + Memo / Note now.\n\nExample:\nTransfer: 123ABC\nMemo: 7788\nNotes: paid successfully',
      orderCreated: 'Your order was sent to admin successfully ✅\nOrder ID:',
      noOrders: 'You do not have orders yet.',
      canceled: 'Canceled ✅',
      unknown: 'I did not understand. Use the buttons or type /start',
      adminOnly: 'Admins only.',
      howItWorks: 'How it works:\n1) Tap Send session.\n2) Paste your session in one message.\n3) Choose payment method.\n4) After paying, send transfer code and memo/note.\n5) Admin reviews and approves your order.'
    }
  }
};

const BOT_TOKEN = process.env.BOT_TOKEN;
const PUBLIC_URL = process.env.PUBLIC_URL;
const PORT = Number(process.env.PORT || 3000);
const ADMIN_IDS = (process.env.ADMIN_IDS || process.env.ADMIN_ID || '')
  .split(',')
  .map((x) => Number(x.trim()))
  .filter(Boolean);

if (!BOT_TOKEN) throw new Error('BOT_TOKEN is required');
if (!process.env.DATABASE_URL) throw new Error('DATABASE_URL is required');

const pool = new Pool({
  connectionString: process.env.DATABASE_URL,
  ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false
});

const bot = new Telegraf(BOT_TOKEN);
bot.use(session());

function t(lang, key) {
  return APP_CONFIG.texts[lang]?.[key] || APP_CONFIG.texts.ar[key] || key;
}

function isAdmin(ctx) {
  return ADMIN_IDS.includes(ctx.from?.id);
}

async function initDb() {
  await pool.query(`
    CREATE TABLE IF NOT EXISTS users (
      telegram_id BIGINT PRIMARY KEY,
      username TEXT,
      first_name TEXT,
      language TEXT DEFAULT 'ar',
      created_at TIMESTAMPTZ DEFAULT NOW(),
      updated_at TIMESTAMPTZ DEFAULT NOW()
    );
  `);

  await pool.query(`
    CREATE TABLE IF NOT EXISTS payment_orders (
      id SERIAL PRIMARY KEY,
      telegram_id BIGINT REFERENCES users(telegram_id),
      session_text TEXT,
      payment_method TEXT,
      payment_title TEXT,
      payment_proof TEXT,
      status TEXT DEFAULT 'pending',
      admin_note TEXT,
      created_at TIMESTAMPTZ DEFAULT NOW(),
      updated_at TIMESTAMPTZ DEFAULT NOW()
    );
  `);
}

async function upsertUser(ctx, language) {
  const from = ctx.from;
  if (!from) return;
  const currentLang = await getUserLanguageSafe(from.id);
  const lang = language || currentLang || APP_CONFIG.defaultLanguage;
  await pool.query(
    `INSERT INTO users (telegram_id, username, first_name, language, updated_at)
     VALUES ($1, $2, $3, $4, NOW())
     ON CONFLICT (telegram_id)
     DO UPDATE SET username = EXCLUDED.username, first_name = EXCLUDED.first_name, updated_at = NOW()`,
    [from.id, from.username || null, from.first_name || null, lang]
  );
}

async function getUserLanguageSafe(telegramId) {
  try {
    const result = await pool.query('SELECT language FROM users WHERE telegram_id=$1', [telegramId]);
    return result.rows[0]?.language;
  } catch {
    return null;
  }
}

async function getUserLanguage(ctx) {
  return (await getUserLanguageSafe(ctx.from?.id)) || APP_CONFIG.defaultLanguage;
}

async function setUserLanguage(telegramId, language) {
  await pool.query('UPDATE users SET language=$1, updated_at=NOW() WHERE telegram_id=$2', [language, telegramId]);
}

function mainKeyboard(lang) {
  return Markup.inlineKeyboard([
    [Markup.button.callback(`🔐 ${t(lang, 'sendSession')}`, 'flow:start_session')],
    [Markup.button.webApp(`🌐 ${t(lang, 'openSite')}`, APP_CONFIG.siteUrl)],
    [Markup.button.callback(`📦 ${t(lang, 'myOrders')}`, 'menu:orders'), Markup.button.callback('ℹ️ شرح', 'menu:help')],
    [Markup.button.callback(`🌍 ${t(lang, 'language')}`, 'menu:language'), Markup.button.url(`💬 ${t(lang, 'support')}`, APP_CONFIG.supportUrl)]
  ]);
}

function languageKeyboard() {
  return Markup.inlineKeyboard([
    [Markup.button.callback('العربية 🇮🇶', 'lang:ar'), Markup.button.callback('English 🇬🇧', 'lang:en')]
  ]);
}

function backKeyboard(lang, target = 'menu:main') {
  return Markup.inlineKeyboard([[Markup.button.callback(`⬅️ ${t(lang, 'back')}`, target)]]);
}

function paymentKeyboard(lang) {
  const rows = APP_CONFIG.paymentMethods.map((m) => [
    Markup.button.callback(`💳 ${m.title[lang] || m.title.ar}`, `pay:${m.id}`)
  ]);
  rows.push([Markup.button.callback(`⬅️ ${t(lang, 'back')}`, 'menu:main')]);
  return Markup.inlineKeyboard(rows);
}

async function showMain(ctx, edit = false) {
  const lang = await getUserLanguage(ctx);
  const text = `${APP_CONFIG.projectName[lang]}\n\n${t(lang, 'start')}\n\n${t(lang, 'mainMenu')}`;
  if (edit && ctx.callbackQuery) return ctx.editMessageText(text, mainKeyboard(lang));
  return ctx.reply(text, mainKeyboard(lang));
}

bot.start(async (ctx) => {
  await upsertUser(ctx, APP_CONFIG.defaultLanguage);
  await ctx.reply(t(APP_CONFIG.defaultLanguage, 'chooseLang'), languageKeyboard());
});

bot.command('cancel', async (ctx) => {
  ctx.session = {};
  const lang = await getUserLanguage(ctx);
  await ctx.reply(t(lang, 'canceled'), mainKeyboard(lang));
});

bot.action('menu:main', async (ctx) => {
  await ctx.answerCbQuery();
  ctx.session = {};
  await showMain(ctx, true);
});

bot.action('menu:help', async (ctx) => {
  await ctx.answerCbQuery();
  const lang = await getUserLanguage(ctx);
  await ctx.editMessageText(t(lang, 'howItWorks'), backKeyboard(lang));
});

bot.action('menu:language', async (ctx) => {
  await ctx.answerCbQuery();
  const lang = await getUserLanguage(ctx);
  await ctx.editMessageText(t(lang, 'chooseLang'), languageKeyboard());
});

bot.action(/^lang:(ar|en)$/, async (ctx) => {
  const lang = ctx.match[1];
  await upsertUser(ctx, lang);
  await setUserLanguage(ctx.from.id, lang);
  await ctx.answerCbQuery(t(lang, 'savedLang'));
  await ctx.editMessageText(t(lang, 'savedLang'));
  await showMain(ctx);
});

bot.action('flow:start_session', async (ctx) => {
  await ctx.answerCbQuery();
  const lang = await getUserLanguage(ctx);
  ctx.session = { step: 'waiting_session' };
  await ctx.editMessageText(t(lang, 'sessionPrompt'), Markup.inlineKeyboard([[Markup.button.callback(`❌ ${t(lang, 'cancel')}`, 'menu:main')]]));
});

bot.action(/^pay:(.+)$/, async (ctx) => {
  await ctx.answerCbQuery();
  const lang = await getUserLanguage(ctx);
  const method = APP_CONFIG.paymentMethods.find((m) => m.id === ctx.match[1]);
  if (!ctx.session?.sessionText || !method) return ctx.reply(t(lang, 'unknown'), mainKeyboard(lang));

  ctx.session.paymentMethod = method.id;
  ctx.session.paymentTitle = method.title[lang] || method.title.ar;
  ctx.session.step = 'waiting_payment_proof';

  await ctx.editMessageText(
    `${method.details[lang] || method.details.ar}\n\n${t(lang, 'sendPaymentProof')}`,
    Markup.inlineKeyboard([[Markup.button.callback(`⬅️ ${t(lang, 'back')}`, 'flow:choose_payment')]])
  );
});

bot.action('flow:choose_payment', async (ctx) => {
  await ctx.answerCbQuery();
  const lang = await getUserLanguage(ctx);
  if (!ctx.session?.sessionText) return ctx.editMessageText(t(lang, 'unknown'), mainKeyboard(lang));
  ctx.session.step = 'choosing_payment';
  await ctx.editMessageText(t(lang, 'sessionSaved'), paymentKeyboard(lang));
});

bot.action('menu:orders', async (ctx) => {
  await ctx.answerCbQuery();
  const lang = await getUserLanguage(ctx);
  const result = await pool.query(
    'SELECT id, payment_title, status, created_at FROM payment_orders WHERE telegram_id=$1 ORDER BY id DESC LIMIT 10',
    [ctx.from.id]
  );

  if (!result.rows.length) {
    return ctx.editMessageText(t(lang, 'noOrders'), backKeyboard(lang));
  }

  const lines = result.rows.map((o) => `#${o.id} — ${o.payment_title || '-'}\nStatus: ${o.status}\nDate: ${new Date(o.created_at).toLocaleString()}`);
  await ctx.editMessageText(lines.join('\n\n'), backKeyboard(lang));
});

bot.on('text', async (ctx) => {
  await upsertUser(ctx);
  const lang = await getUserLanguage(ctx);
  const text = ctx.message.text.trim();

  if (ctx.session?.step === 'waiting_session') {
    ctx.session.sessionText = text;
    ctx.session.step = 'choosing_payment';
    return ctx.reply(t(lang, 'sessionSaved'), paymentKeyboard(lang));
  }

  if (ctx.session?.step === 'waiting_payment_proof') {
    const sessionText = ctx.session.sessionText;
    const paymentMethod = ctx.session.paymentMethod;
    const paymentTitle = ctx.session.paymentTitle;
    const paymentProof = text;

    const result = await pool.query(
      `INSERT INTO payment_orders (telegram_id, session_text, payment_method, payment_title, payment_proof, status)
       VALUES ($1, $2, $3, $4, $5, 'pending') RETURNING id`,
      [ctx.from.id, sessionText, paymentMethod, paymentTitle, paymentProof]
    );

    const orderId = result.rows[0].id;
    ctx.session = {};

    await ctx.reply(`${t(lang, 'orderCreated')} #${orderId}`, mainKeyboard(lang));

    const adminText =
      `🆕 طلب دفع جديد #${orderId}\n` +
      `User: ${ctx.from.first_name || ''} @${ctx.from.username || 'none'} (${ctx.from.id})\n` +
      `Payment: ${paymentTitle}\n\n` +
      `🔐 Session:\n${sessionText}\n\n` +
      `🧾 Transfer/Memo:\n${paymentProof}\n\n` +
      `قبول: /approve ${orderId}\nرفض: /reject ${orderId}`;

    for (const adminId of ADMIN_IDS) {
      await ctx.telegram.sendMessage(adminId, adminText.slice(0, 3900)).catch(() => {});
    }
    return;
  }

  return ctx.reply(t(lang, 'unknown'), mainKeyboard(lang));
});

bot.command('admin', async (ctx) => {
  if (!isAdmin(ctx)) return ctx.reply(t(await getUserLanguage(ctx), 'adminOnly'));
  await ctx.reply('Admin panel:\n/orders - latest orders\n/approve ORDER_ID\n/reject ORDER_ID\n/broadcast message');
});

bot.command('orders', async (ctx) => {
  if (!isAdmin(ctx)) return ctx.reply(t(await getUserLanguage(ctx), 'adminOnly'));
  const result = await pool.query('SELECT * FROM payment_orders ORDER BY id DESC LIMIT 15');
  if (!result.rows.length) return ctx.reply('No orders yet.');
  const text = result.rows.map((o) =>
    `#${o.id} ${o.status}\nUser: ${o.telegram_id}\nPayment: ${o.payment_title || '-'}\nSession: ${o.session_text || '-'}\nProof: ${o.payment_proof || '-'}`
  ).join('\n\n');
  await ctx.reply(text.slice(0, 3900));
});

bot.command('approve', async (ctx) => updateOrderStatus(ctx, 'approved'));
bot.command('reject', async (ctx) => updateOrderStatus(ctx, 'rejected'));

async function updateOrderStatus(ctx, status) {
  if (!isAdmin(ctx)) return ctx.reply(t(await getUserLanguage(ctx), 'adminOnly'));
  const id = Number(ctx.message.text.split(/\s+/)[1]);
  if (!id) return ctx.reply('Usage: /approve ORDER_ID or /reject ORDER_ID');

  const result = await pool.query('UPDATE payment_orders SET status=$1, updated_at=NOW() WHERE id=$2 RETURNING *', [status, id]);
  if (!result.rows.length) return ctx.reply('Order not found.');

  const order = result.rows[0];
  await ctx.reply(`Order #${id} updated to ${status}.`);
  await ctx.telegram.sendMessage(order.telegram_id, `طلبك #${id} صار: ${status}`).catch(() => {});
}

bot.command('broadcast', async (ctx) => {
  if (!isAdmin(ctx)) return ctx.reply(t(await getUserLanguage(ctx), 'adminOnly'));
  const message = ctx.message.text.replace('/broadcast', '').trim();
  if (!message) return ctx.reply('Usage: /broadcast your message');

  const result = await pool.query('SELECT telegram_id FROM users');
  let sent = 0;
  for (const row of result.rows) {
    await ctx.telegram.sendMessage(row.telegram_id, message).then(() => sent++).catch(() => {});
  }
  await ctx.reply(`Broadcast sent to ${sent} users.`);
});

const app = express();
app.use(express.json());

app.get('/', (_, res) => res.send('Payment Assistant bot is running ✅'));
app.get('/health', (_, res) => res.json({ ok: true, time: new Date().toISOString() }));
app.use('/telegram', bot.webhookCallback('/telegram'));

await initDb();

if (process.env.NODE_ENV === 'production' && PUBLIC_URL) {
  await bot.telegram.setWebhook(`${PUBLIC_URL.replace(/\/$/, '')}/telegram`);
  app.listen(PORT, () => console.log(`Server running on port ${PORT}`));
} else {
  await bot.launch();
  console.log('Bot running in polling mode');
}

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
