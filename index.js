import 'dotenv/config';
import express from 'express';
import pg from 'pg';
import { Telegraf, Markup, session } from 'telegraf';

const { Pool } = pg;

/*
  ============================================================
  عدّل هنا فقط أغلب الأشياء التي تحتاجها مستقبلاً
  ============================================================
*/
const APP_CONFIG = {
  projectName: {
    ar: 'مساعد GPT للدفع والخدمات',
    en: 'GPT Payment & Services Assistant'
  },

  siteUrl: process.env.SITE_URL || 'https://gpt.aide.freespaces.app/',
  supportUrl: process.env.SUPPORT_URL || 'https://t.me/t4i44s',
  defaultLanguage: 'ar',

  // عدّل المنتجات حسب نظام الموقع الحقيقي
  products: [
    {
      id: 'gpt_super',
      name: { ar: 'اشتراك GPT Super', en: 'GPT Super Subscription' },
      description: {
        ar: 'خدمة GPT حسب المتوفر في الموقع. يتم تأكيد الطلب من الإدارة.',
        en: 'GPT service based on site availability. Order is confirmed by admin.'
      },
      priceText: { ar: 'حسب السعر الحالي', en: 'Based on current price' }
    },
    {
      id: 'gpt_account',
      name: { ar: 'حساب GPT', en: 'GPT Account' },
      description: {
        ar: 'صيغة التسليم حسب المنتج: mail | password إن كان متوفراً.',
        en: 'Delivery format depends on product: mail | password if available.'
      },
      priceText: { ar: 'حسب السعر الحالي', en: 'Based on current price' }
    },
    {
      id: 'balance_topup',
      name: { ar: 'شحن رصيد', en: 'Balance Top-up' },
      description: {
        ar: 'ارسل رمز التحويل ورمز الملاحظة حتى يتم الشحن تلقائياً أو مراجعته.',
        en: 'Send transfer code and memo/note code so your balance can be topped up or reviewed.'
      },
      priceText: { ar: 'حسب المبلغ', en: 'Custom amount' }
    }
  ],

  paymentMethods: [
    {
      id: 'usdt_trc20',
      title: { ar: 'USDT TRC20', en: 'USDT TRC20' },
      details: {
        ar: 'ضع هنا عنوان محفظتك. مهم جداً: أرسل رمز التحويل ورمز الملاحظة.',
        en: 'Put your wallet address here. Important: send transfer code and memo/note code.'
      }
    },
    {
      id: 'binance_pay',
      title: { ar: 'Binance Pay', en: 'Binance Pay' },
      details: {
        ar: 'ضع هنا Binance Pay ID أو رابط الدفع.',
        en: 'Put your Binance Pay ID or payment link here.'
      }
    }
  ],

  texts: {
    ar: {
      start: 'هلا بيك 👋\nاختر شنو تريد من الأزرار بالأسفل. تگدر تستخدم البوت بدل الدخول للموقع، وتگدر هم تفتح الموقع من زر WebApp.',
      chooseLang: 'اختر اللغة / Choose language',
      mainMenu: 'القائمة الرئيسية:',
      products: 'الخدمات والمنتجات:',
      openSite: 'فتح الموقع',
      language: 'اللغة',
      support: 'الدعم',
      myOrders: 'طلباتي',
      newOrder: 'طلب جديد',
      back: 'رجوع',
      orderPrompt: 'اكتب الكمية أو التفاصيل المطلوبة لهذا الطلب:',
      paymentPrompt: 'اختر طريقة الدفع:',
      sendReceipt: 'أرسل الآن رمز التحويل + رمز الملاحظة + أي ملاحظات.\nمثال:\nTransfer: 123ABC\nMemo: 7788\nNotes: أريد حساب واحد',
      orderCreated: 'تم إنشاء طلبك بنجاح ✅\nرقم الطلب:',
      noOrders: 'ما عندك طلبات بعد.',
      profile: 'حسابي',
      savedLang: 'تم حفظ اللغة ✅',
      adminOnly: 'هذا الأمر للإدارة فقط.',
      canceled: 'تم الإلغاء.',
      unknown: 'ما فهمت عليك. استخدم الأزرار أو اكتب /start'
    },
    en: {
      start: 'Welcome 👋\nChoose what you need from the buttons below. You can use the bot instead of entering the website, or open the site with the WebApp button.',
      chooseLang: 'Choose language / اختر اللغة',
      mainMenu: 'Main menu:',
      products: 'Services and products:',
      openSite: 'Open site',
      language: 'Language',
      support: 'Support',
      myOrders: 'My orders',
      newOrder: 'New order',
      back: 'Back',
      orderPrompt: 'Write the quantity or required details for this order:',
      paymentPrompt: 'Choose payment method:',
      sendReceipt: 'Now send transfer code + memo/note code + any notes.\nExample:\nTransfer: 123ABC\nMemo: 7788\nNotes: I need one account',
      orderCreated: 'Your order was created successfully ✅\nOrder ID:',
      noOrders: 'You do not have orders yet.',
      profile: 'My profile',
      savedLang: 'Language saved ✅',
      adminOnly: 'Admins only.',
      canceled: 'Canceled.',
      unknown: 'I did not understand. Use the buttons or type /start'
    }
  }
};

const BOT_TOKEN = process.env.BOT_TOKEN;
const PUBLIC_URL = process.env.PUBLIC_URL;
const PORT = Number(process.env.PORT || 3000);
const ADMIN_IDS = (process.env.ADMIN_IDS || '')
  .split(',')
  .map((x) => Number(x.trim()))
  .filter(Boolean);

if (!BOT_TOKEN) {
  throw new Error('BOT_TOKEN is required');
}
if (!process.env.DATABASE_URL) {
  throw new Error('DATABASE_URL is required');
}

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
    CREATE TABLE IF NOT EXISTS orders (
      id SERIAL PRIMARY KEY,
      telegram_id BIGINT REFERENCES users(telegram_id),
      product_id TEXT,
      product_name TEXT,
      details TEXT,
      payment_method TEXT,
      receipt TEXT,
      status TEXT DEFAULT 'pending',
      created_at TIMESTAMPTZ DEFAULT NOW(),
      updated_at TIMESTAMPTZ DEFAULT NOW()
    );
  `);
}

async function upsertUser(ctx, language) {
  const from = ctx.from;
  const lang = language || APP_CONFIG.defaultLanguage;
  await pool.query(
    `INSERT INTO users (telegram_id, username, first_name, language, updated_at)
     VALUES ($1, $2, $3, $4, NOW())
     ON CONFLICT (telegram_id)
     DO UPDATE SET username = EXCLUDED.username, first_name = EXCLUDED.first_name, updated_at = NOW()`,
    [from.id, from.username || null, from.first_name || null, lang]
  );
}

async function setUserLanguage(telegramId, language) {
  await pool.query('UPDATE users SET language=$1, updated_at=NOW() WHERE telegram_id=$2', [language, telegramId]);
}

async function getUserLanguage(ctx) {
  const telegramId = ctx.from?.id;
  if (!telegramId) return APP_CONFIG.defaultLanguage;
  const result = await pool.query('SELECT language FROM users WHERE telegram_id=$1', [telegramId]);
  return result.rows[0]?.language || APP_CONFIG.defaultLanguage;
}

function mainKeyboard(lang) {
  return Markup.inlineKeyboard([
    [Markup.button.callback(`🛒 ${t(lang, 'newOrder')}`, 'menu:products')],
    [Markup.button.webApp(`🌐 ${t(lang, 'openSite')}`, APP_CONFIG.siteUrl)],
    [Markup.button.callback(`📦 ${t(lang, 'myOrders')}`, 'menu:orders'), Markup.button.callback(`👤 ${t(lang, 'profile')}`, 'menu:profile')],
    [Markup.button.callback(`🌍 ${t(lang, 'language')}`, 'menu:language'), Markup.button.url(`💬 ${t(lang, 'support')}`, APP_CONFIG.supportUrl)]
  ]);
}

function languageKeyboard() {
  return Markup.inlineKeyboard([
    [Markup.button.callback('العربية 🇮🇶', 'lang:ar'), Markup.button.callback('English 🇬🇧', 'lang:en')]
  ]);
}

function productsKeyboard(lang) {
  const rows = APP_CONFIG.products.map((p) => [Markup.button.callback(`🛍 ${p.name[lang] || p.name.ar}`, `product:${p.id}`)]);
  rows.push([Markup.button.callback(`⬅️ ${t(lang, 'back')}`, 'menu:main')]);
  return Markup.inlineKeyboard(rows);
}

function paymentKeyboard(lang) {
  const rows = APP_CONFIG.paymentMethods.map((m) => [Markup.button.callback(`💳 ${m.title[lang] || m.title.ar}`, `pay:${m.id}`)]);
  rows.push([Markup.button.callback(`⬅️ ${t(lang, 'back')}`, 'menu:products')]);
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
  await showMain(ctx, true);
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

bot.action('menu:products', async (ctx) => {
  await ctx.answerCbQuery();
  const lang = await getUserLanguage(ctx);
  await ctx.editMessageText(t(lang, 'products'), productsKeyboard(lang));
});

bot.action(/^product:(.+)$/, async (ctx) => {
  await ctx.answerCbQuery();
  const lang = await getUserLanguage(ctx);
  const product = APP_CONFIG.products.find((p) => p.id === ctx.match[1]);
  if (!product) return ctx.reply(t(lang, 'unknown'));

  ctx.session.order = { productId: product.id };
  const text = `🛍 ${product.name[lang] || product.name.ar}\n${product.description[lang] || product.description.ar}\n💵 ${product.priceText[lang] || product.priceText.ar}\n\n${t(lang, 'orderPrompt')}`;
  await ctx.editMessageText(text, Markup.inlineKeyboard([[Markup.button.callback(`⬅️ ${t(lang, 'back')}`, 'menu:products')]]));
});

bot.action(/^pay:(.+)$/, async (ctx) => {
  await ctx.answerCbQuery();
  const lang = await getUserLanguage(ctx);
  const method = APP_CONFIG.paymentMethods.find((m) => m.id === ctx.match[1]);
  if (!ctx.session.order || !method) return ctx.reply(t(lang, 'unknown'));

  ctx.session.order.paymentMethod = method.id;
  ctx.session.step = 'waiting_receipt';
  await ctx.editMessageText(`💳 ${method.title[lang] || method.title.ar}\n${method.details[lang] || method.details.ar}\n\n${t(lang, 'sendReceipt')}`);
});

bot.action('menu:orders', async (ctx) => {
  await ctx.answerCbQuery();
  const lang = await getUserLanguage(ctx);
  const result = await pool.query(
    'SELECT id, product_name, status, created_at FROM orders WHERE telegram_id=$1 ORDER BY id DESC LIMIT 10',
    [ctx.from.id]
  );

  if (!result.rows.length) {
    return ctx.editMessageText(t(lang, 'noOrders'), Markup.inlineKeyboard([[Markup.button.callback(`⬅️ ${t(lang, 'back')}`, 'menu:main')]]));
  }

  const lines = result.rows.map((o) => `#${o.id} — ${o.product_name}\nStatus: ${o.status}\nDate: ${new Date(o.created_at).toLocaleString()}`);
  await ctx.editMessageText(lines.join('\n\n'), Markup.inlineKeyboard([[Markup.button.callback(`⬅️ ${t(lang, 'back')}`, 'menu:main')]]));
});

bot.action('menu:profile', async (ctx) => {
  await ctx.answerCbQuery();
  const lang = await getUserLanguage(ctx);
  const result = await pool.query('SELECT COUNT(*)::int AS count FROM orders WHERE telegram_id=$1', [ctx.from.id]);
  const count = result.rows[0]?.count || 0;
  await ctx.editMessageText(
    `👤 ${t(lang, 'profile')}\nID: ${ctx.from.id}\nUsername: @${ctx.from.username || 'none'}\nOrders: ${count}`,
    Markup.inlineKeyboard([[Markup.button.callback(`⬅️ ${t(lang, 'back')}`, 'menu:main')]])
  );
});

bot.on('text', async (ctx) => {
  await upsertUser(ctx);
  const lang = await getUserLanguage(ctx);

  if (ctx.session?.order && !ctx.session.step) {
    ctx.session.order.details = ctx.message.text;
    ctx.session.step = 'waiting_payment';
    return ctx.reply(t(lang, 'paymentPrompt'), paymentKeyboard(lang));
  }

  if (ctx.session?.order && ctx.session.step === 'waiting_receipt') {
    const product = APP_CONFIG.products.find((p) => p.id === ctx.session.order.productId);
    const productName = product?.name[lang] || product?.name.ar || ctx.session.order.productId;
    const receipt = ctx.message.text;

    const result = await pool.query(
      `INSERT INTO orders (telegram_id, product_id, product_name, details, payment_method, receipt, status)
       VALUES ($1, $2, $3, $4, $5, $6, 'pending') RETURNING id`,
      [ctx.from.id, ctx.session.order.productId, productName, ctx.session.order.details, ctx.session.order.paymentMethod, receipt]
    );

    const orderId = result.rows[0].id;
    ctx.session = {};

    await ctx.reply(`${t(lang, 'orderCreated')} #${orderId}`, mainKeyboard(lang));

    for (const adminId of ADMIN_IDS) {
      await ctx.telegram.sendMessage(
        adminId,
        `🆕 New order #${orderId}\nUser: ${ctx.from.first_name || ''} @${ctx.from.username || 'none'} (${ctx.from.id})\nProduct: ${productName}\nDetails: ${ctx.session?.order?.details || 'saved'}\nPayment: ${receipt}\n\nApprove: /approve ${orderId}\nReject: /reject ${orderId}`
      ).catch(() => {});
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
  const result = await pool.query('SELECT * FROM orders ORDER BY id DESC LIMIT 15');
  if (!result.rows.length) return ctx.reply('No orders yet.');
  const text = result.rows.map((o) => `#${o.id} ${o.status}\nUser: ${o.telegram_id}\nProduct: ${o.product_name}\nDetails: ${o.details || '-'}\nPayment: ${o.payment_method || '-'}\nReceipt: ${o.receipt || '-'}`).join('\n\n');
  await ctx.reply(text.slice(0, 3900));
});

bot.command('approve', async (ctx) => updateOrderStatus(ctx, 'approved'));
bot.command('reject', async (ctx) => updateOrderStatus(ctx, 'rejected'));

async function updateOrderStatus(ctx, status) {
  if (!isAdmin(ctx)) return ctx.reply(t(await getUserLanguage(ctx), 'adminOnly'));
  const id = Number(ctx.message.text.split(/\s+/)[1]);
  if (!id) return ctx.reply('Usage: /approve ORDER_ID or /reject ORDER_ID');

  const result = await pool.query('UPDATE orders SET status=$1, updated_at=NOW() WHERE id=$2 RETURNING *', [status, id]);
  if (!result.rows.length) return ctx.reply('Order not found.');

  const order = result.rows[0];
  await ctx.reply(`Order #${id} updated to ${status}.`);
  await ctx.telegram.sendMessage(order.telegram_id, `Order #${id} status: ${status}`).catch(() => {});
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

// مكان الربط الحقيقي مع API الموقع إذا توفر لاحقاً
const siteApi = {
  async getProductsFromSite() {
    // مثال مستقبلي:
    // const response = await fetch(`${APP_CONFIG.siteUrl}/api/products`);
    // return response.json();
    return APP_CONFIG.products;
  }
};

const app = express();
app.use(express.json());

app.get('/', (_, res) => {
  res.send('Telegram bot is running ✅');
});

app.get('/health', (_, res) => {
  res.json({ ok: true, time: new Date().toISOString() });
});

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
