import express from 'express';
import { Telegraf, Markup } from 'telegraf';
import pg from 'pg';

const { Pool } = pg;

// =========================
// إعدادات سهلة التعديل
// =========================
const CONFIG = {
  BOT_TOKEN: process.env.BOT_TOKEN,
  ADMIN_IDS: (process.env.ADMIN_IDS || process.env.ADMIN_ID || '')
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean),
  PORT: Number(process.env.PORT || 3000),
  DATABASE_URL: process.env.DATABASE_URL,
  SITE_URL: process.env.SITE_URL || 'https://gpt.aide.freespaces.app/',
  SUPPORT_URL: process.env.SUPPORT_URL || 'https://t.me/t4i44s',
};

const TEXT = {
  ar: {
    welcome:
      '🤖 أهلاً بك في مساعد الدفع\n\nاختَر من الأزرار بالأسفل. افتح الموقع داخل تلگرام، وبعد ما تكمل الخطوات هناك ارجع للبوت وسجّل طلب الدفع.',
    chooseLang: '🌐 اختر اللغة / Choose language',
    mainMenu: '🏠 القائمة الرئيسية',
    openSite: '🌐 افتح مساعد الدفع',
    newOrder: '🧾 تسجيل طلب دفع',
    prices: '💳 أنواع الاشتراك والعملات',
    support: '☎️ الدعم',
    choosePlan: 'اختر نوع الاشتراك:',
    chooseCurrency: 'اختر الدولة / العملة:',
    choosePayment: 'اختر طريقة الدفع:',
    sendTransfer: 'أرسل الآن رمز التحويل / Transaction ID:',
    sendMemo: 'أرسل رمز الملاحظة / Memo / Note حتى لا تضيع الأموال:',
    sendProof: 'أرسل صورة إثبات الدفع أو اضغط تخطي:',
    skip: 'تخطي',
    confirm: '✅ تأكيد وإرسال الطلب',
    cancel: '❌ إلغاء',
    cancelled: 'تم إلغاء العملية.',
    saved: '✅ تم إرسال طلبك بنجاح. انتظر مراجعة الأدمن.',
    noOrders: 'لا توجد طلبات بعد.',
    adminOnly: 'هذا الأمر للأدمن فقط.',
    askUseSite:
      '⚠️ ملاحظة مهمة:\nافتح الموقع من الزر بالأسفل وأكمل خطوات مساعد الدفع هناك. البوت لا يطلب كلمات مرور أو بيانات دخول حساسة. بعد ما تحصل على تفاصيل الدفع ارجع هنا وسجّل رمز التحويل والملاحظة.',
  },
  en: {
    welcome:
      '🤖 Welcome to Payment Assistant\n\nUse the buttons below. Open the website inside Telegram, complete the steps there, then return to the bot and submit your payment request.',
    chooseLang: '🌐 اختر اللغة / Choose language',
    mainMenu: '🏠 Main menu',
    openSite: '🌐 Open Payment Assistant',
    newOrder: '🧾 Submit payment request',
    prices: '💳 Plans and currencies',
    support: '☎️ Support',
    choosePlan: 'Choose subscription type:',
    chooseCurrency: 'Choose country / currency:',
    choosePayment: 'Choose payment method:',
    sendTransfer: 'Send the Transaction ID:',
    sendMemo: 'Send the Memo / Note code:',
    sendProof: 'Send payment proof image or press Skip:',
    skip: 'Skip',
    confirm: '✅ Confirm and submit',
    cancel: '❌ Cancel',
    cancelled: 'Operation cancelled.',
    saved: '✅ Your request was submitted. Please wait for admin review.',
    noOrders: 'No orders yet.',
    adminOnly: 'Admin only.',
    askUseSite:
      '⚠️ Important:\nOpen the website using the button below and complete the payment assistant steps there. This bot does not ask for passwords or sensitive login data. Then return here and submit the transaction ID and memo.',
  },
};

const PLANS = [
  ['plus', 'ChatGPT Plus'],
  ['go', 'ChatGPT Go'],
  ['pro', 'ChatGPT Pro'],
  ['team_full', 'فريق مفتوح بسعر كامل / Team full price'],
  ['team_1', 'تفعيل الفريق مقابل 1$ / Team activation 1$'],
  ['plus_0_us', 'ChatGPT Plus 0$ US'],
  ['plus_0_uk', 'ChatGPT Plus 0$ UK'],
  ['plus_0_jp', 'ChatGPT Plus 0$ Japan'],
  ['refund_vn', 'رمز استرداد Plus 0$ Vietnam'],
  ['refund_sg', 'رمز استرداد Plus 0$ Singapore'],
];

const CURRENCIES = [
  ['usd', '💳 الدولار الأمريكي USD'],
  ['gbp', '💳 الجنيه الإسترليني GBP'],
  ['eur', '💳 اليورو EUR'],
  ['inr', '💳 الروبية الهندية INR'],
  ['idr', '💳 الروبية الإندونيسية IDR'],
  ['pkr', '💳 الروبية الباكستانية PKR'],
  ['thb', '💳 البات التايلندي THB'],
  ['myr', '💳 الرينغت الماليزي MYR'],
];

const PAYMENT_METHODS = [
  ['binance', 'Binance Pay'],
  ['usdt_trc20', 'USDT TRC20'],
  ['usdt_bep20', 'USDT BEP20'],
  ['iraqi_wallet', 'محفظة عراقية'],
  ['manual', 'دفع يدوي / Manual'],
];

const userState = new Map();

if (!CONFIG.BOT_TOKEN) throw new Error('BOT_TOKEN is required');
const bot = new Telegraf(CONFIG.BOT_TOKEN);
const app = express();
app.use(express.json());

const pool = CONFIG.DATABASE_URL
  ? new Pool({ connectionString: CONFIG.DATABASE_URL, ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false })
  : null;

async function initDb() {
  if (!pool) return;
  await pool.query(`
    CREATE TABLE IF NOT EXISTS users (
      telegram_id TEXT PRIMARY KEY,
      username TEXT,
      first_name TEXT,
      language TEXT DEFAULT 'ar',
      created_at TIMESTAMP DEFAULT NOW()
    );
  `);
  await pool.query(`
    CREATE TABLE IF NOT EXISTS orders (
      id SERIAL PRIMARY KEY,
      telegram_id TEXT NOT NULL,
      username TEXT,
      plan_key TEXT,
      plan_name TEXT,
      currency_key TEXT,
      currency_name TEXT,
      payment_key TEXT,
      payment_name TEXT,
      transaction_id TEXT,
      memo TEXT,
      proof_file_id TEXT,
      status TEXT DEFAULT 'pending',
      admin_note TEXT,
      created_at TIMESTAMP DEFAULT NOW(),
      updated_at TIMESTAMP DEFAULT NOW()
    );
  `);
}

function isAdmin(ctx) {
  return CONFIG.ADMIN_IDS.includes(String(ctx.from?.id));
}

function getLang(ctx) {
  return userState.get(ctx.from?.id)?.lang || 'ar';
}

function t(ctx, key) {
  return TEXT[getLang(ctx)]?.[key] || TEXT.ar[key];
}

function mainKeyboard(ctx) {
  return Markup.inlineKeyboard([
    [Markup.button.webApp(t(ctx, 'openSite'), CONFIG.SITE_URL)],
    [Markup.button.callback(t(ctx, 'newOrder'), 'new_order')],
    [Markup.button.callback(t(ctx, 'prices'), 'plans_info')],
    [Markup.button.url(t(ctx, 'support'), CONFIG.SUPPORT_URL)],
    [Markup.button.callback('العربية 🇮🇶', 'lang_ar'), Markup.button.callback('English 🇬🇧', 'lang_en')],
  ]);
}

function backCancelKeyboard(ctx) {
  return Markup.inlineKeyboard([[Markup.button.callback(t(ctx, 'cancel'), 'cancel')]]);
}

function buttonsFrom(items, prefix, columns = 1) {
  const rows = [];
  for (let i = 0; i < items.length; i += columns) {
    rows.push(items.slice(i, i + columns).map(([key, label]) => Markup.button.callback(label, `${prefix}:${key}`)));
  }
  rows.push([Markup.button.callback('❌ إلغاء / Cancel', 'cancel')]);
  return Markup.inlineKeyboard(rows);
}

async function saveUser(ctx, lang = 'ar') {
  if (!pool || !ctx.from) return;
  await pool.query(
    `INSERT INTO users (telegram_id, username, first_name, language)
     VALUES ($1,$2,$3,$4)
     ON CONFLICT (telegram_id) DO UPDATE SET username=$2, first_name=$3, language=$4`,
    [String(ctx.from.id), ctx.from.username || '', ctx.from.first_name || '', lang]
  );
}

async function createOrder(ctx, data) {
  if (!pool) return { id: Date.now() };
  const res = await pool.query(
    `INSERT INTO orders
    (telegram_id, username, plan_key, plan_name, currency_key, currency_name, payment_key, payment_name, transaction_id, memo, proof_file_id)
    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11)
    RETURNING id`,
    [
      String(ctx.from.id),
      ctx.from.username || '',
      data.planKey,
      data.planName,
      data.currencyKey,
      data.currencyName,
      data.paymentKey,
      data.paymentName,
      data.transactionId,
      data.memo,
      data.proofFileId || '',
    ]
  );
  return res.rows[0];
}

function orderSummary(data, id = '') {
  return `🧾 طلب دفع جديد ${id ? '#' + id : ''}\n\n` +
    `👤 المستخدم: ${data.firstName || '-'} @${data.username || '-'}\n` +
    `🆔 Telegram ID: ${data.telegramId}\n\n` +
    `📦 الاشتراك: ${data.planName}\n` +
    `💱 العملة: ${data.currencyName}\n` +
    `💳 الدفع: ${data.paymentName}\n\n` +
    `🔢 رمز التحويل: ${data.transactionId}\n` +
    `📝 الملاحظة/Memo: ${data.memo}\n` +
    `📸 إثبات: ${data.proofFileId ? 'مرفق' : 'غير مرفق'}\n\n` +
    `الحالة: pending`;
}

async function notifyAdmins(ctx, data, orderId) {
  const msg = orderSummary(data, orderId);
  for (const adminId of CONFIG.ADMIN_IDS) {
    try {
      await ctx.telegram.sendMessage(adminId, msg, {
        reply_markup: {
          inline_keyboard: [[
            { text: '✅ قبول', callback_data: `admin_approve:${orderId}` },
            { text: '❌ رفض', callback_data: `admin_reject:${orderId}` },
          ]],
        },
      });
      if (data.proofFileId) await ctx.telegram.sendPhoto(adminId, data.proofFileId, { caption: `📸 إثبات الدفع للطلب #${orderId}` });
    } catch (e) {
      console.error('Admin notify failed', adminId, e.message);
    }
  }
}

bot.start(async (ctx) => {
  const current = userState.get(ctx.from.id) || { lang: 'ar' };
  userState.set(ctx.from.id, current);
  await saveUser(ctx, current.lang);
  await ctx.reply(t(ctx, 'welcome'), mainKeyboard(ctx));
});

bot.command('admin', async (ctx) => {
  if (!isAdmin(ctx)) return ctx.reply(t(ctx, 'adminOnly'));
  return ctx.reply('⚙️ أوامر الأدمن:\n/orders\n/order رقم\n/approve رقم\n/reject رقم السبب\n/broadcast النص');
});

bot.command('orders', async (ctx) => {
  if (!isAdmin(ctx)) return ctx.reply(t(ctx, 'adminOnly'));
  if (!pool) return ctx.reply('DATABASE_URL غير مفعّل.');
  const res = await pool.query(`SELECT * FROM orders ORDER BY id DESC LIMIT 10`);
  if (!res.rows.length) return ctx.reply(t(ctx, 'noOrders'));
  const text = res.rows.map((o) => `#${o.id} | ${o.status}\n${o.plan_name}\n${o.currency_name}\n${o.payment_name}\nTX: ${o.transaction_id}\nMemo: ${o.memo}\nUser: @${o.username || '-'} / ${o.telegram_id}`).join('\n\n');
  return ctx.reply(text);
});

bot.command('order', async (ctx) => {
  if (!isAdmin(ctx)) return ctx.reply(t(ctx, 'adminOnly'));
  if (!pool) return ctx.reply('DATABASE_URL غير مفعّل.');
  const id = ctx.message.text.split(/\s+/)[1];
  if (!id) return ctx.reply('اكتب: /order 1');
  const res = await pool.query(`SELECT * FROM orders WHERE id=$1`, [id]);
  if (!res.rows.length) return ctx.reply('الطلب غير موجود.');
  const o = res.rows[0];
  await ctx.reply(`🧾 الطلب #${o.id}\nالحالة: ${o.status}\nالمستخدم: @${o.username || '-'} / ${o.telegram_id}\nالاشتراك: ${o.plan_name}\nالعملة: ${o.currency_name}\nالدفع: ${o.payment_name}\nرمز التحويل: ${o.transaction_id}\nMemo: ${o.memo}`);
  if (o.proof_file_id) await ctx.replyWithPhoto(o.proof_file_id, { caption: `إثبات الطلب #${o.id}` });
});

async function setOrderStatus(ctx, id, status, note = '') {
  if (!pool) return ctx.reply('DATABASE_URL غير مفعّل.');
  const res = await pool.query(`UPDATE orders SET status=$1, admin_note=$2, updated_at=NOW() WHERE id=$3 RETURNING *`, [status, note, id]);
  if (!res.rows.length) return ctx.reply('الطلب غير موجود.');
  const o = res.rows[0];
  await ctx.reply(`تم تحديث الطلب #${id} إلى ${status}.`);
  try {
    const userMsg = status === 'approved'
      ? `✅ تم قبول طلبك #${id}.`
      : `❌ تم رفض طلبك #${id}.${note ? '\nالسبب: ' + note : ''}`;
    await ctx.telegram.sendMessage(o.telegram_id, userMsg);
  } catch {}
}

bot.command('approve', async (ctx) => {
  if (!isAdmin(ctx)) return ctx.reply(t(ctx, 'adminOnly'));
  const id = ctx.message.text.split(/\s+/)[1];
  if (!id) return ctx.reply('اكتب: /approve 1');
  return setOrderStatus(ctx, id, 'approved');
});

bot.command('reject', async (ctx) => {
  if (!isAdmin(ctx)) return ctx.reply(t(ctx, 'adminOnly'));
  const parts = ctx.message.text.split(/\s+/);
  const id = parts[1];
  const note = parts.slice(2).join(' ');
  if (!id) return ctx.reply('اكتب: /reject 1 السبب');
  return setOrderStatus(ctx, id, 'rejected', note);
});

bot.command('broadcast', async (ctx) => {
  if (!isAdmin(ctx)) return ctx.reply(t(ctx, 'adminOnly'));
  if (!pool) return ctx.reply('DATABASE_URL غير مفعّل.');
  const msg = ctx.message.text.replace('/broadcast', '').trim();
  if (!msg) return ctx.reply('اكتب الرسالة بعد الأمر.');
  const res = await pool.query('SELECT telegram_id FROM users');
  let sent = 0;
  for (const u of res.rows) {
    try { await ctx.telegram.sendMessage(u.telegram_id, msg); sent++; } catch {}
  }
  return ctx.reply(`تم الإرسال إلى ${sent} مستخدم.`);
});

bot.action('lang_ar', async (ctx) => {
  userState.set(ctx.from.id, { ...(userState.get(ctx.from.id) || {}), lang: 'ar' });
  await saveUser(ctx, 'ar');
  await ctx.answerCbQuery('تم اختيار العربية');
  await ctx.editMessageText(TEXT.ar.welcome, mainKeyboard(ctx));
});

bot.action('lang_en', async (ctx) => {
  userState.set(ctx.from.id, { ...(userState.get(ctx.from.id) || {}), lang: 'en' });
  await saveUser(ctx, 'en');
  await ctx.answerCbQuery('English selected');
  await ctx.editMessageText(TEXT.en.welcome, mainKeyboard(ctx));
});

bot.action('plans_info', async (ctx) => {
  const text = '📦 الأنواع المتوفرة:\n\n' + PLANS.map(([, v]) => `• ${v}`).join('\n') + '\n\n💱 العملات:\n' + CURRENCIES.map(([, v]) => `• ${v}`).join('\n');
  await ctx.answerCbQuery();
  await ctx.reply(text, mainKeyboard(ctx));
});

bot.action('new_order', async (ctx) => {
  userState.set(ctx.from.id, { lang: getLang(ctx), step: 'plan', order: {} });
  await ctx.answerCbQuery();
  await ctx.reply(t(ctx, 'askUseSite'), Markup.inlineKeyboard([
    [Markup.button.webApp(t(ctx, 'openSite'), CONFIG.SITE_URL)],
    [Markup.button.callback('➡️ متابعة تسجيل الطلب', 'continue_order')],
    [Markup.button.callback(t(ctx, 'cancel'), 'cancel')],
  ]));
});

bot.action('continue_order', async (ctx) => {
  const s = userState.get(ctx.from.id) || { lang: 'ar', order: {} };
  s.step = 'plan';
  userState.set(ctx.from.id, s);
  await ctx.answerCbQuery();
  await ctx.reply(t(ctx, 'choosePlan'), buttonsFrom(PLANS, 'plan'));
});

bot.action(/^plan:(.+)$/, async (ctx) => {
  const key = ctx.match[1];
  const item = PLANS.find(([k]) => k === key);
  const s = userState.get(ctx.from.id) || { lang: 'ar', order: {} };
  s.order.planKey = key;
  s.order.planName = item?.[1] || key;
  s.step = 'currency';
  userState.set(ctx.from.id, s);
  await ctx.answerCbQuery();
  await ctx.reply(t(ctx, 'chooseCurrency'), buttonsFrom(CURRENCIES, 'currency'));
});

bot.action(/^currency:(.+)$/, async (ctx) => {
  const key = ctx.match[1];
  const item = CURRENCIES.find(([k]) => k === key);
  const s = userState.get(ctx.from.id) || { lang: 'ar', order: {} };
  s.order.currencyKey = key;
  s.order.currencyName = item?.[1] || key;
  s.step = 'payment';
  userState.set(ctx.from.id, s);
  await ctx.answerCbQuery();
  await ctx.reply(t(ctx, 'choosePayment'), buttonsFrom(PAYMENT_METHODS, 'payment'));
});

bot.action(/^payment:(.+)$/, async (ctx) => {
  const key = ctx.match[1];
  const item = PAYMENT_METHODS.find(([k]) => k === key);
  const s = userState.get(ctx.from.id) || { lang: 'ar', order: {} };
  s.order.paymentKey = key;
  s.order.paymentName = item?.[1] || key;
  s.step = 'transaction';
  userState.set(ctx.from.id, s);
  await ctx.answerCbQuery();
  await ctx.reply(t(ctx, 'sendTransfer'), backCancelKeyboard(ctx));
});

bot.action('skip_proof', async (ctx) => {
  const s = userState.get(ctx.from.id);
  if (!s?.order) return ctx.answerCbQuery();
  s.order.proofFileId = '';
  s.step = 'confirm';
  userState.set(ctx.from.id, s);
  await ctx.answerCbQuery();
  await ctx.reply(orderSummary({
    ...s.order,
    telegramId: ctx.from.id,
    username: ctx.from.username,
    firstName: ctx.from.first_name,
  }), Markup.inlineKeyboard([
    [Markup.button.callback(t(ctx, 'confirm'), 'confirm_order')],
    [Markup.button.callback(t(ctx, 'cancel'), 'cancel')],
  ]));
});

bot.action('confirm_order', async (ctx) => {
  const s = userState.get(ctx.from.id);
  if (!s?.order) return ctx.answerCbQuery();
  const data = {
    ...s.order,
    telegramId: ctx.from.id,
    username: ctx.from.username || '',
    firstName: ctx.from.first_name || '',
  };
  const row = await createOrder(ctx, data);
  await notifyAdmins(ctx, data, row.id);
  userState.set(ctx.from.id, { lang: s.lang || 'ar' });
  await ctx.answerCbQuery();
  await ctx.reply(t(ctx, 'saved'), mainKeyboard(ctx));
});

bot.action(/^admin_approve:(\d+)$/, async (ctx) => {
  if (!isAdmin(ctx)) return ctx.answerCbQuery('Admin only');
  await ctx.answerCbQuery('Approved');
  return setOrderStatus(ctx, ctx.match[1], 'approved');
});

bot.action(/^admin_reject:(\d+)$/, async (ctx) => {
  if (!isAdmin(ctx)) return ctx.answerCbQuery('Admin only');
  await ctx.answerCbQuery('Rejected');
  return setOrderStatus(ctx, ctx.match[1], 'rejected');
});

bot.action('cancel', async (ctx) => {
  const lang = getLang(ctx);
  userState.set(ctx.from.id, { lang });
  await ctx.answerCbQuery();
  await ctx.reply(t(ctx, 'cancelled'), mainKeyboard(ctx));
});

bot.on('photo', async (ctx) => {
  const s = userState.get(ctx.from.id);
  if (!s || s.step !== 'proof') return;
  const photos = ctx.message.photo;
  s.order.proofFileId = photos[photos.length - 1].file_id;
  s.step = 'confirm';
  userState.set(ctx.from.id, s);
  await ctx.reply(orderSummary({
    ...s.order,
    telegramId: ctx.from.id,
    username: ctx.from.username,
    firstName: ctx.from.first_name,
  }), Markup.inlineKeyboard([
    [Markup.button.callback(t(ctx, 'confirm'), 'confirm_order')],
    [Markup.button.callback(t(ctx, 'cancel'), 'cancel')],
  ]));
});

bot.on('text', async (ctx) => {
  const s = userState.get(ctx.from.id);
  if (!s?.step) return ctx.reply(t(ctx, 'mainMenu'), mainKeyboard(ctx));
  const text = ctx.message.text.trim();
  if (text === '/start') return;

  if (s.step === 'transaction') {
    s.order.transactionId = text;
    s.step = 'memo';
    userState.set(ctx.from.id, s);
    return ctx.reply(t(ctx, 'sendMemo'), backCancelKeyboard(ctx));
  }

  if (s.step === 'memo') {
    s.order.memo = text;
    s.step = 'proof';
    userState.set(ctx.from.id, s);
    return ctx.reply(t(ctx, 'sendProof'), Markup.inlineKeyboard([
      [Markup.button.callback(t(ctx, 'skip'), 'skip_proof')],
      [Markup.button.callback(t(ctx, 'cancel'), 'cancel')],
    ]));
  }
});

app.get('/', (req, res) => res.send('Payment Assistant Bot is running ✅'));
app.get('/health', (req, res) => res.json({ ok: true }));

async function start() {
  await initDb();
  await bot.launch();
  app.listen(CONFIG.PORT, () => console.log(`Server running on ${CONFIG.PORT}`));
  console.log('Telegram bot started');
}

start().catch((err) => {
  console.error(err);
  process.exit(1);
});

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
