import express from 'express';
import { Telegraf, Markup } from 'telegraf';
import pg from 'pg';

const { Pool } = pg;

// =====================================================
// مساعد الدفع - كل التعديل من هنا فقط
// =====================================================
const CONFIG = {
  BOT_TOKEN: process.env.BOT_TOKEN,
  ADMIN_IDS: (process.env.ADMIN_IDS || process.env.ADMIN_ID || '')
    .split(',')
    .map((x) => x.trim())
    .filter(Boolean),
  PORT: Number(process.env.PORT || 3000),
  DATABASE_URL: process.env.DATABASE_URL,
  SITE_URL: process.env.SITE_URL || 'https://gpt.aide.freespaces.app/',
  API_BASE: process.env.API_BASE || 'https://gpt.serve.freespaces.app',
  SUPPORT_URL: process.env.SUPPORT_URL || 'https://t.me/t4i44s',
  REQUEST_TIMEOUT: 90000,
};

// API المعروف من ملف الموقع + محاولات تلقائية للأزرار التي لم يظهر مسارها بعد
const SITE_ENDPOINTS = {
  login: '/api/user/login',
  info: '/api/user/info',
  logout: '/api/user/logout',
  register: '/api/user/free/register',

  // البوت يجربها بالترتيب، أول endpoint يرجع نجاح يستخدمه
  paymentLinks: [
    '/api/payment/link',
    '/api/payment/create',
    '/api/pay/link',
    '/api/pay/create',
    '/api/order/create',
    '/api/order/pay',
    '/api/subscription/payment/link',
    '/api/subscription/create',
    '/api/stripe/payment/link',
    '/api/account/payment-link',
  ],
  autoRenewOn: [
    '/api/subscription/auto-renew/enable',
    '/api/subscription/renew/enable',
    '/api/account/auto-renew/enable',
    '/api/user/auto-renew/enable',
  ],
  autoRenewOff: [
    '/api/subscription/auto-renew/disable',
    '/api/subscription/renew/disable',
    '/api/account/auto-renew/disable',
    '/api/user/auto-renew/disable',
  ],
  invoices: [
    '/api/invoice/list',
    '/api/invoices',
    '/api/payment/invoices',
    '/api/order/list',
    '/api/bill/list',
  ],
  teamAutoPull: [
    '/api/team/auto-pull',
    '/api/team/pull',
    '/api/subscription/team/pull',
  ],
};

const PLANS = [
  ['chatgpt_plus', 'ChatGPT Plus'],
  ['chatgpt_go', 'ChatGPT GO'],
  ['chatgpt_pro', 'ChatGPT Pro'],
  ['team_full', 'فريق مفتوح بسعر كامل'],
  ['plus_0_us', '0$ ChatGPT Plus - الولايات المتحدة'],
  ['plus_0_uk', 'فعالية Plus 0$ - المملكة المتحدة'],
  ['plus_0_jp', 'فعالية Plus 0$ - اليابان'],
  ['refund_vn', 'رمز استرداد Plus 0$ - فيتنام'],
  ['refund_sg', 'رمز استرداد Plus 0$ - سنغافورة'],
  ['team_free_year', 'خصم سنوي مجاني للجنود على ChatGPT Plus'],
  ['team_activate_free', 'فعّل فريقك مجاناً'],
  ['team_1usd', 'دولار واحد لتفعيل الفريق'],
];

const CURRENCIES = [
  ['USD', '💳 الدولار الأمريكي - الولايات المتحدة'],
  ['GBP', '💳 الجنيه الإسترليني - المملكة المتحدة'],
  ['EUR', '💳 اليورو - الاتحاد الأوروبي'],
  ['INR', '💳 الروبية الهندية - الهند'],
  ['IDR', '💳 الروبية الإندونيسية - إندونيسيا'],
  ['PKR', '💳 الروبية الباكستانية - باكستان'],
  ['THB', '💳 البات التايلندي - تايلاند'],
  ['MYR', '💳 الرينغت الماليزي - ماليزيا'],
];

const PAYMENT_METHODS = [
  ['auto', '⚡ توليد رابط الدفع من الموقع'],
  ['binance', 'Binance Pay'],
  ['usdt_trc20', 'USDT TRC20'],
  ['usdt_bep20', 'USDT BEP20'],
  ['manual', 'دفع يدوي'],
];

const TEXT = {
  ar: {
    welcome: '🤖 أهلاً بك في مساعد الدفع\n\nهذا البوت مرتب حتى يتحكم بالموقع من الأزرار قدر الإمكان، ويفتح الموقع مباشر عند الحاجة.',
    menu: '🏠 القائمة الرئيسية',
    openSite: '🌐 فتح الموقع',
    loginSite: '🔐 تسجيل دخول الموقع',
    siteInfo: '👤 معلومات حساب الموقع',
    paymentLinks: '🔗 احصل على روابط دفع الاشتراك',
    teamPull: '👥 يقوم الفريق تلقائياً بالسحب',
    renewOn: '✅ تفعيل التجديد التلقائي',
    renewOff: '❌ إيقاف التجديد التلقائي',
    invoices: '📄 رابط لاستعراض الفواتير السابقة',
    newOrder: '🧾 تسجيل دفع يدوي',
    support: '☎️ الدعم',
    choosePlan: 'اختر نوع الاشتراك:',
    chooseCurrency: 'اختر الدولة / العملة:',
    choosePayment: 'اختر طريقة الدفع:',
    askUsername: 'أرسل اسم مستخدم الموقع:',
    askPassword: 'أرسل كلمة مرور الموقع:',
    loggedIn: '✅ تم تسجيل الدخول وحفظ توكن الموقع بنجاح.',
    needLogin: '⚠️ سجل دخول الموقع أولاً من زر 🔐 تسجيل دخول الموقع.',
    working: '⏳ جاري الاتصال بالموقع...',
    noDirectApi: '⚠️ لم يرجع الموقع رابط دفع من المسارات المجربة. افتح الموقع من الزر وأكمل الخطوة هناك. إذا حصلت مسار API جديد، ضعه أعلى index.js داخل SITE_ENDPOINTS.',
    sendTransfer: 'أرسل رمز التحويل / Transaction ID:',
    sendMemo: 'أرسل رمز الملاحظة / Memo / Note:',
    sendProof: 'أرسل صورة إثبات الدفع أو اضغط تخطي:',
    skip: 'تخطي',
    confirm: '✅ تأكيد وإرسال',
    cancel: '❌ إلغاء',
    cancelled: 'تم إلغاء العملية.',
    saved: '✅ تم إرسال الطلب للأدمن.',
    adminOnly: 'هذا الأمر للأدمن فقط.',
  },
  en: {
    welcome: '🤖 Welcome to Payment Assistant\n\nThis bot is arranged to control the website through buttons whenever the site API allows it.',
    menu: '🏠 Main menu',
    openSite: '🌐 Open website',
    loginSite: '🔐 Site login',
    siteInfo: '👤 Site account info',
    paymentLinks: '🔗 Get subscription payment links',
    teamPull: '👥 Team auto pull',
    renewOn: '✅ Enable auto renew',
    renewOff: '❌ Disable auto renew',
    invoices: '📄 Previous invoices',
    newOrder: '🧾 Manual payment record',
    support: '☎️ Support',
    choosePlan: 'Choose subscription type:',
    chooseCurrency: 'Choose country / currency:',
    choosePayment: 'Choose payment method:',
    askUsername: 'Send site username:',
    askPassword: 'Send site password:',
    loggedIn: '✅ Logged in and saved site token.',
    needLogin: '⚠️ Login to the site first.',
    working: '⏳ Connecting to website...',
    noDirectApi: '⚠️ No payment link returned from tried endpoints. Open the website and complete it there. Add the API path to SITE_ENDPOINTS when known.',
    sendTransfer: 'Send Transaction ID:',
    sendMemo: 'Send Memo / Note:',
    sendProof: 'Send proof image or press Skip:',
    skip: 'Skip',
    confirm: '✅ Confirm and submit',
    cancel: '❌ Cancel',
    cancelled: 'Cancelled.',
    saved: '✅ Request sent to admin.',
    adminOnly: 'Admin only.',
  },
};

const userState = new Map();
if (!CONFIG.BOT_TOKEN) throw new Error('BOT_TOKEN is required');

const bot = new Telegraf(CONFIG.BOT_TOKEN);
const app = express();
app.use(express.json());

const pool = CONFIG.DATABASE_URL
  ? new Pool({
      connectionString: CONFIG.DATABASE_URL,
      ssl: process.env.NODE_ENV === 'production' ? { rejectUnauthorized: false } : false,
    })
  : null;

async function initDb() {
  if (!pool) return;
  await pool.query(`
    CREATE TABLE IF NOT EXISTS users (
      telegram_id TEXT PRIMARY KEY,
      username TEXT,
      first_name TEXT,
      language TEXT DEFAULT 'ar',
      created_at TIMESTAMP DEFAULT NOW(),
      updated_at TIMESTAMP DEFAULT NOW()
    );
  `);
  await pool.query(`
    CREATE TABLE IF NOT EXISTS site_sessions (
      telegram_id TEXT PRIMARY KEY,
      site_username TEXT,
      site_token TEXT,
      raw_login JSONB,
      created_at TIMESTAMP DEFAULT NOW(),
      updated_at TIMESTAMP DEFAULT NOW()
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
      site_payment_url TEXT,
      transaction_id TEXT,
      memo TEXT,
      proof_file_id TEXT,
      status TEXT DEFAULT 'pending',
      raw_site_response JSONB,
      admin_note TEXT,
      created_at TIMESTAMP DEFAULT NOW(),
      updated_at TIMESTAMP DEFAULT NOW()
    );
  `);
}

function isAdmin(ctx) {
  return CONFIG.ADMIN_IDS.includes(String(ctx.from?.id));
}
function lang(ctx) {
  return userState.get(ctx.from?.id)?.lang || 'ar';
}
function tr(ctx, key) {
  return TEXT[lang(ctx)]?.[key] || TEXT.ar[key] || key;
}
function getState(ctx) {
  const id = ctx.from.id;
  if (!userState.has(id)) userState.set(id, { lang: 'ar' });
  return userState.get(id);
}
function setStep(ctx, step, patch = {}) {
  const s = { ...getState(ctx), step, ...patch };
  userState.set(ctx.from.id, s);
  return s;
}
function rows(items, prefix, columns = 1) {
  const out = [];
  for (let i = 0; i < items.length; i += columns) {
    out.push(items.slice(i, i + columns).map(([k, label]) => Markup.button.callback(label, `${prefix}:${k}`)));
  }
  out.push([Markup.button.callback('⬅️ رجوع / Back', 'menu')]);
  return Markup.inlineKeyboard(out);
}
function mainKeyboard(ctx) {
  return Markup.inlineKeyboard([
    [Markup.button.webApp(tr(ctx, 'openSite'), CONFIG.SITE_URL)],
    [Markup.button.callback(tr(ctx, 'loginSite'), 'site_login'), Markup.button.callback(tr(ctx, 'siteInfo'), 'site_info')],
    [Markup.button.callback(tr(ctx, 'paymentLinks'), 'pay_start')],
    [Markup.button.callback(tr(ctx, 'teamPull'), 'team_pull')],
    [Markup.button.callback(tr(ctx, 'renewOn'), 'renew_on'), Markup.button.callback(tr(ctx, 'renewOff'), 'renew_off')],
    [Markup.button.callback(tr(ctx, 'invoices'), 'invoices')],
    [Markup.button.callback(tr(ctx, 'newOrder'), 'manual_order')],
    [Markup.button.url(tr(ctx, 'support'), CONFIG.SUPPORT_URL)],
    [Markup.button.callback('العربية 🇮🇶', 'lang_ar'), Markup.button.callback('English 🇬🇧', 'lang_en')],
  ]);
}
async function saveUser(ctx) {
  if (!pool || !ctx.from) return;
  await pool.query(
    `INSERT INTO users (telegram_id, username, first_name, language, updated_at)
     VALUES ($1,$2,$3,$4,NOW())
     ON CONFLICT (telegram_id) DO UPDATE SET username=$2, first_name=$3, language=$4, updated_at=NOW()`,
    [String(ctx.from.id), ctx.from.username || '', ctx.from.first_name || '', lang(ctx)]
  );
}

async function siteRequest(path, options = {}, timeout = CONFIG.REQUEST_TIMEOUT) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), timeout);
  try {
    const res = await fetch(`${CONFIG.API_BASE}${path}`, { ...options, signal: controller.signal });
    const text = await res.text();
    clearTimeout(timer);
    let json;
    try { json = JSON.parse(text); } catch { json = { code: res.status, message: text, data: null }; }
    return { ok: res.ok, status: res.status, json, path };
  } catch (e) {
    clearTimeout(timer);
    return { ok: false, status: 0, path, json: { code: e.name === 'AbortError' ? 408 : 500, message: e.message, data: null } };
  }
}
function extractToken(loginJson) {
  return loginJson?.data?.token || loginJson?.data?.accessToken || loginJson?.data?.authorization || loginJson?.token || loginJson?.accessToken || loginJson?.authorization || '';
}
function authHeader(token) {
  if (!token) return {};
  return token.toLowerCase().startsWith('bearer ') ? { Authorization: token } : { Authorization: token };
}
function isSuccess(j) {
  return j && (j.code === 0 || j.code === 200 || j.success === true || j.status === 'success' || j.data || j.url || j.paymentUrl || j.link);
}
function findUrl(obj) {
  const seen = new Set();
  function walk(x) {
    if (!x || typeof x !== 'object' || seen.has(x)) return '';
    seen.add(x);
    for (const [k, v] of Object.entries(x)) {
      if (typeof v === 'string' && /^https?:\/\//i.test(v) && /(pay|checkout|invoice|stripe|payment|openai|chatgpt)/i.test(v)) return v;
      if (typeof v === 'object') { const r = walk(v); if (r) return r; }
    }
    return '';
  }
  return walk(obj);
}
async function getSiteSession(telegramId) {
  if (!pool) return null;
  const res = await pool.query('SELECT * FROM site_sessions WHERE telegram_id=$1', [String(telegramId)]);
  return res.rows[0] || null;
}
async function saveSiteSession(ctx, username, token, raw) {
  if (!pool) return;
  await pool.query(
    `INSERT INTO site_sessions (telegram_id, site_username, site_token, raw_login, updated_at)
     VALUES ($1,$2,$3,$4,NOW())
     ON CONFLICT (telegram_id) DO UPDATE SET site_username=$2, site_token=$3, raw_login=$4, updated_at=NOW()`,
    [String(ctx.from.id), username, token, raw]
  );
}
async function callFirst(paths, token, body = {}, method = 'POST') {
  let last = null;
  for (const p of paths) {
    const req = await siteRequest(p, {
      method,
      headers: { 'Content-Type': 'application/json', ...authHeader(token) },
      ...(method === 'GET' ? {} : { body: JSON.stringify(body) }),
    });
    last = req;
    if (req.ok && isSuccess(req.json)) return req;
  }
  return last;
}
function formatSiteJson(res) {
  const j = res?.json || res;
  const small = JSON.stringify(j, null, 2);
  return small.length > 3500 ? small.slice(0, 3500) + '\n...TRUNCATED' : small;
}

async function loginToSite(username, password) {
  const res = await siteRequest(SITE_ENDPOINTS.login, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ username, password }),
  });
  return res;
}
async function getSiteInfo(token) {
  return siteRequest(SITE_ENDPOINTS.info, {
    method: 'GET',
    headers: { 'Content-Type': 'application/json', ...authHeader(token) },
  });
}

function orderSummary(data, id = '') {
  return `🧾 طلب دفع ${id ? '#' + id : ''}\n\n` +
    `👤 المستخدم: ${data.firstName || '-'} @${data.username || '-'}\n` +
    `🆔 Telegram ID: ${data.telegramId}\n\n` +
    `📦 الاشتراك: ${data.planName || '-'}\n` +
    `💱 العملة: ${data.currencyName || '-'}\n` +
    `💳 طريقة الدفع: ${data.paymentName || '-'}\n` +
    `🔗 رابط الموقع: ${data.sitePaymentUrl || '-'}\n\n` +
    `🔢 رمز التحويل: ${data.transactionId || '-'}\n` +
    `📝 Memo: ${data.memo || '-'}\n` +
    `📸 إثبات: ${data.proofFileId ? 'مرفق' : 'غير مرفق'}`;
}
async function createOrder(ctx, data) {
  if (!pool) return { id: Date.now() };
  const res = await pool.query(
    `INSERT INTO orders
    (telegram_id, username, plan_key, plan_name, currency_key, currency_name, payment_key, payment_name, site_payment_url, transaction_id, memo, proof_file_id, raw_site_response)
    VALUES ($1,$2,$3,$4,$5,$6,$7,$8,$9,$10,$11,$12,$13)
    RETURNING id`,
    [String(ctx.from.id), ctx.from.username || '', data.planKey || '', data.planName || '', data.currencyKey || '', data.currencyName || '', data.paymentKey || '', data.paymentName || '', data.sitePaymentUrl || '', data.transactionId || '', data.memo || '', data.proofFileId || '', data.rawSiteResponse || null]
  );
  return res.rows[0];
}
async function notifyAdmins(ctx, data, orderId) {
  for (const adminId of CONFIG.ADMIN_IDS) {
    try {
      await ctx.telegram.sendMessage(adminId, orderSummary(data, orderId), {
        reply_markup: { inline_keyboard: [[
          { text: '✅ قبول', callback_data: `admin_approve:${orderId}` },
          { text: '❌ رفض', callback_data: `admin_reject:${orderId}` },
        ]] },
      });
      if (data.proofFileId) await ctx.telegram.sendPhoto(adminId, data.proofFileId, { caption: `📸 إثبات الدفع #${orderId}` });
    } catch (e) { console.error('admin notify failed', e.message); }
  }
}
async function setOrderStatus(ctx, id, status, note = '') {
  if (!pool) return ctx.reply('DATABASE_URL غير مفعّل.');
  const res = await pool.query('UPDATE orders SET status=$1, admin_note=$2, updated_at=NOW() WHERE id=$3 RETURNING *', [status, note, id]);
  if (!res.rows.length) return ctx.reply('الطلب غير موجود.');
  const o = res.rows[0];
  await ctx.reply(`تم تحديث الطلب #${id} إلى ${status}.`);
  try {
    await ctx.telegram.sendMessage(o.telegram_id, status === 'approved' ? `✅ تم قبول طلبك #${id}.` : `❌ تم رفض طلبك #${id}.${note ? '\n' + note : ''}`);
  } catch {}
}

bot.start(async (ctx) => {
  getState(ctx);
  await saveUser(ctx);
  await ctx.reply(tr(ctx, 'welcome'), mainKeyboard(ctx));
});
bot.action('menu', async (ctx) => {
  setStep(ctx, null, { temp: null, order: null });
  await ctx.answerCbQuery();
  await ctx.reply(tr(ctx, 'menu'), mainKeyboard(ctx));
});
bot.action('lang_ar', async (ctx) => {
  setStep(ctx, null, { lang: 'ar' });
  await saveUser(ctx);
  await ctx.answerCbQuery('العربية');
  await ctx.reply(TEXT.ar.welcome, mainKeyboard(ctx));
});
bot.action('lang_en', async (ctx) => {
  setStep(ctx, null, { lang: 'en' });
  await saveUser(ctx);
  await ctx.answerCbQuery('English');
  await ctx.reply(TEXT.en.welcome, mainKeyboard(ctx));
});

bot.action('site_login', async (ctx) => {
  setStep(ctx, 'site_username', { temp: {} });
  await ctx.answerCbQuery();
  await ctx.reply(tr(ctx, 'askUsername'), Markup.inlineKeyboard([[Markup.button.callback(tr(ctx, 'cancel'), 'menu')]]));
});
bot.action('site_info', async (ctx) => {
  await ctx.answerCbQuery();
  const session = await getSiteSession(ctx.from.id);
  if (!session?.site_token) return ctx.reply(tr(ctx, 'needLogin'), mainKeyboard(ctx));
  await ctx.reply(tr(ctx, 'working'));
  const res = await getSiteInfo(session.site_token);
  await ctx.reply(`👤 معلومات الموقع:\n\n<pre>${escapeHtml(formatSiteJson(res))}</pre>`, { parse_mode: 'HTML', ...mainKeyboard(ctx) });
});

async function directSiteAction(ctx, paths, label) {
  await ctx.answerCbQuery();
  const session = await getSiteSession(ctx.from.id);
  if (!session?.site_token) return ctx.reply(tr(ctx, 'needLogin'), mainKeyboard(ctx));
  await ctx.reply(tr(ctx, 'working'));
  const res = await callFirst(paths, session.site_token, {}, 'POST');
  const url = findUrl(res?.json);
  if (url) return ctx.reply(`${label}\n\n${url}`, Markup.inlineKeyboard([[Markup.button.url('فتح الرابط', url)], [Markup.button.callback('🏠 القائمة', 'menu')]]));
  return ctx.reply(`${label}\n\n<pre>${escapeHtml(formatSiteJson(res))}</pre>`, { parse_mode: 'HTML', ...mainKeyboard(ctx) });
}
bot.action('team_pull', (ctx) => directSiteAction(ctx, SITE_ENDPOINTS.teamAutoPull, '👥 نتيجة سحب الفريق'));
bot.action('renew_on', (ctx) => directSiteAction(ctx, SITE_ENDPOINTS.autoRenewOn, '✅ نتيجة تفعيل التجديد'));
bot.action('renew_off', (ctx) => directSiteAction(ctx, SITE_ENDPOINTS.autoRenewOff, '❌ نتيجة إيقاف التجديد'));
bot.action('invoices', async (ctx) => {
  await ctx.answerCbQuery();
  const session = await getSiteSession(ctx.from.id);
  if (!session?.site_token) return ctx.reply(tr(ctx, 'needLogin'), mainKeyboard(ctx));
  await ctx.reply(tr(ctx, 'working'));
  const res = await callFirst(SITE_ENDPOINTS.invoices, session.site_token, {}, 'GET');
  const url = findUrl(res?.json);
  if (url) return ctx.reply(`📄 الفواتير:\n${url}`, Markup.inlineKeyboard([[Markup.button.url('فتح الفواتير', url)], [Markup.button.callback('🏠 القائمة', 'menu')]]));
  await ctx.reply(`📄 الفواتير:\n\n<pre>${escapeHtml(formatSiteJson(res))}</pre>`, { parse_mode: 'HTML', ...mainKeyboard(ctx) });
});

bot.action('pay_start', async (ctx) => {
  setStep(ctx, 'pay_plan', { order: {} });
  await ctx.answerCbQuery();
  await ctx.reply(tr(ctx, 'choosePlan'), rows(PLANS, 'pay_plan'));
});
bot.action(/^pay_plan:(.+)$/, async (ctx) => {
  const item = PLANS.find(([k]) => k === ctx.match[1]);
  const s = getState(ctx);
  s.order = { ...(s.order || {}), planKey: ctx.match[1], planName: item?.[1] || ctx.match[1] };
  s.step = 'pay_currency';
  userState.set(ctx.from.id, s);
  await ctx.answerCbQuery();
  await ctx.reply(tr(ctx, 'chooseCurrency'), rows(CURRENCIES, 'pay_currency'));
});
bot.action(/^pay_currency:(.+)$/, async (ctx) => {
  const item = CURRENCIES.find(([k]) => k === ctx.match[1]);
  const s = getState(ctx);
  s.order = { ...(s.order || {}), currencyKey: ctx.match[1], currencyName: item?.[1] || ctx.match[1] };
  s.step = 'pay_method';
  userState.set(ctx.from.id, s);
  await ctx.answerCbQuery();
  await ctx.reply(tr(ctx, 'choosePayment'), rows(PAYMENT_METHODS, 'pay_method'));
});
bot.action(/^pay_method:(.+)$/, async (ctx) => {
  const method = PAYMENT_METHODS.find(([k]) => k === ctx.match[1]);
  const s = getState(ctx);
  s.order = { ...(s.order || {}), paymentKey: ctx.match[1], paymentName: method?.[1] || ctx.match[1] };
  await ctx.answerCbQuery();

  if (ctx.match[1] === 'auto') {
    const session = await getSiteSession(ctx.from.id);
    if (!session?.site_token) return ctx.reply(tr(ctx, 'needLogin'), mainKeyboard(ctx));
    await ctx.reply(tr(ctx, 'working'));
    const payload = {
      planType: s.order.planKey,
      subscriptionType: s.order.planKey,
      type: s.order.planKey,
      currency: s.order.currencyKey,
      countryCurrency: s.order.currencyKey,
      paymentCountry: s.order.currencyKey,
    };
    const res = await callFirst(SITE_ENDPOINTS.paymentLinks, session.site_token, payload, 'POST');
    const url = findUrl(res?.json);
    s.order.rawSiteResponse = res?.json || null;
    if (url) {
      s.order.sitePaymentUrl = url;
      userState.set(ctx.from.id, s);
      return ctx.reply(`✅ تم توليد رابط الدفع:\n${url}\n\nبعد الدفع أرسل رمز التحويل.`, Markup.inlineKeyboard([
        [Markup.button.url('🔗 فتح رابط الدفع', url)],
        [Markup.button.callback('➡️ سجل رمز التحويل', 'after_pay_link')],
        [Markup.button.callback('🏠 القائمة', 'menu')],
      ]));
    }
    await ctx.reply(tr(ctx, 'noDirectApi'), Markup.inlineKeyboard([
      [Markup.button.webApp('🌐 افتح الموقع', CONFIG.SITE_URL)],
      [Markup.button.callback('➡️ متابعة يدوي', 'after_pay_link')],
      [Markup.button.callback('🏠 القائمة', 'menu')],
    ]));
    return;
  }
  s.step = 'transaction';
  userState.set(ctx.from.id, s);
  return ctx.reply(tr(ctx, 'sendTransfer'), Markup.inlineKeyboard([[Markup.button.callback(tr(ctx, 'cancel'), 'menu')]]));
});
bot.action('after_pay_link', async (ctx) => {
  const s = getState(ctx);
  s.step = 'transaction';
  userState.set(ctx.from.id, s);
  await ctx.answerCbQuery();
  await ctx.reply(tr(ctx, 'sendTransfer'), Markup.inlineKeyboard([[Markup.button.callback(tr(ctx, 'cancel'), 'menu')]]));
});

bot.action('manual_order', async (ctx) => {
  setStep(ctx, 'pay_plan', { order: {} });
  await ctx.answerCbQuery();
  await ctx.reply(tr(ctx, 'choosePlan'), rows(PLANS, 'pay_plan'));
});

bot.action('skip_proof', async (ctx) => {
  const s = getState(ctx);
  s.order.proofFileId = '';
  s.step = 'confirm';
  userState.set(ctx.from.id, s);
  await ctx.answerCbQuery();
  await ctx.reply(orderSummary({ ...s.order, telegramId: ctx.from.id, username: ctx.from.username, firstName: ctx.from.first_name }), Markup.inlineKeyboard([
    [Markup.button.callback(tr(ctx, 'confirm'), 'confirm_order')],
    [Markup.button.callback(tr(ctx, 'cancel'), 'menu')],
  ]));
});
bot.action('confirm_order', async (ctx) => {
  const s = getState(ctx);
  const data = { ...(s.order || {}), telegramId: ctx.from.id, username: ctx.from.username || '', firstName: ctx.from.first_name || '' };
  const row = await createOrder(ctx, data);
  await notifyAdmins(ctx, data, row.id);
  setStep(ctx, null, { order: null });
  await ctx.answerCbQuery();
  await ctx.reply(tr(ctx, 'saved'), mainKeyboard(ctx));
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

bot.command('admin', async (ctx) => {
  if (!isAdmin(ctx)) return ctx.reply(tr(ctx, 'adminOnly'));
  await ctx.reply('⚙️ أوامر الأدمن:\n/orders\n/order رقم\n/approve رقم\n/reject رقم السبب\n/broadcast النص\n/site_logout');
});
bot.command('orders', async (ctx) => {
  if (!isAdmin(ctx)) return ctx.reply(tr(ctx, 'adminOnly'));
  if (!pool) return ctx.reply('DATABASE_URL غير مفعّل.');
  const res = await pool.query('SELECT * FROM orders ORDER BY id DESC LIMIT 10');
  if (!res.rows.length) return ctx.reply('لا توجد طلبات.');
  await ctx.reply(res.rows.map(o => `#${o.id} | ${o.status}\n${o.plan_name}\n${o.currency_name}\n${o.payment_name}\nURL: ${o.site_payment_url || '-'}\nTX: ${o.transaction_id || '-'}\nMemo: ${o.memo || '-'}\nUser: @${o.username || '-'} / ${o.telegram_id}`).join('\n\n'));
});
bot.command('order', async (ctx) => {
  if (!isAdmin(ctx)) return ctx.reply(tr(ctx, 'adminOnly'));
  if (!pool) return ctx.reply('DATABASE_URL غير مفعّل.');
  const id = ctx.message.text.split(/\s+/)[1];
  if (!id) return ctx.reply('اكتب: /order 1');
  const res = await pool.query('SELECT * FROM orders WHERE id=$1', [id]);
  if (!res.rows.length) return ctx.reply('الطلب غير موجود.');
  const o = res.rows[0];
  await ctx.reply(orderSummary({
    telegramId: o.telegram_id, username: o.username, planName: o.plan_name, currencyName: o.currency_name,
    paymentName: o.payment_name, sitePaymentUrl: o.site_payment_url, transactionId: o.transaction_id, memo: o.memo, proofFileId: o.proof_file_id,
  }, o.id));
  if (o.proof_file_id) await ctx.replyWithPhoto(o.proof_file_id, { caption: `إثبات #${o.id}` });
});
bot.command('approve', async (ctx) => {
  if (!isAdmin(ctx)) return ctx.reply(tr(ctx, 'adminOnly'));
  const id = ctx.message.text.split(/\s+/)[1];
  if (!id) return ctx.reply('اكتب: /approve 1');
  return setOrderStatus(ctx, id, 'approved');
});
bot.command('reject', async (ctx) => {
  if (!isAdmin(ctx)) return ctx.reply(tr(ctx, 'adminOnly'));
  const [, id, ...rest] = ctx.message.text.split(/\s+/);
  if (!id) return ctx.reply('اكتب: /reject 1 السبب');
  return setOrderStatus(ctx, id, 'rejected', rest.join(' '));
});
bot.command('broadcast', async (ctx) => {
  if (!isAdmin(ctx)) return ctx.reply(tr(ctx, 'adminOnly'));
  if (!pool) return ctx.reply('DATABASE_URL غير مفعّل.');
  const msg = ctx.message.text.replace('/broadcast', '').trim();
  if (!msg) return ctx.reply('اكتب الرسالة بعد الأمر.');
  const res = await pool.query('SELECT telegram_id FROM users');
  let sent = 0;
  for (const u of res.rows) { try { await ctx.telegram.sendMessage(u.telegram_id, msg); sent++; } catch {} }
  await ctx.reply(`تم الإرسال إلى ${sent}.`);
});
bot.command('site_logout', async (ctx) => {
  if (!pool) return ctx.reply('DATABASE_URL غير مفعّل.');
  await pool.query('DELETE FROM site_sessions WHERE telegram_id=$1', [String(ctx.from.id)]);
  await ctx.reply('تم حذف جلسة الموقع من قاعدة البيانات.');
});

bot.on('photo', async (ctx) => {
  const s = getState(ctx);
  if (s.step !== 'proof') return;
  const photos = ctx.message.photo;
  s.order.proofFileId = photos[photos.length - 1].file_id;
  s.step = 'confirm';
  userState.set(ctx.from.id, s);
  await ctx.reply(orderSummary({ ...s.order, telegramId: ctx.from.id, username: ctx.from.username, firstName: ctx.from.first_name }), Markup.inlineKeyboard([
    [Markup.button.callback(tr(ctx, 'confirm'), 'confirm_order')],
    [Markup.button.callback(tr(ctx, 'cancel'), 'menu')],
  ]));
});

bot.on('text', async (ctx) => {
  const s = getState(ctx);
  const text = ctx.message.text.trim();
  if (text.startsWith('/')) return;

  if (s.step === 'site_username') {
    s.temp = { ...(s.temp || {}), siteUsername: text };
    s.step = 'site_password';
    userState.set(ctx.from.id, s);
    return ctx.reply(tr(ctx, 'askPassword'), Markup.inlineKeyboard([[Markup.button.callback(tr(ctx, 'cancel'), 'menu')]]));
  }
  if (s.step === 'site_password') {
    const username = s.temp?.siteUsername || '';
    await ctx.reply(tr(ctx, 'working'));
    const res = await loginToSite(username, text);
    const token = extractToken(res.json);
    if (token) {
      await saveSiteSession(ctx, username, token, res.json);
      setStep(ctx, null, { temp: null });
      return ctx.reply(tr(ctx, 'loggedIn'), mainKeyboard(ctx));
    }
    return ctx.reply(`❌ فشل تسجيل الدخول:\n<pre>${escapeHtml(formatSiteJson(res))}</pre>`, { parse_mode: 'HTML', ...mainKeyboard(ctx) });
  }
  if (s.step === 'transaction') {
    s.order.transactionId = text;
    s.step = 'memo';
    userState.set(ctx.from.id, s);
    return ctx.reply(tr(ctx, 'sendMemo'), Markup.inlineKeyboard([[Markup.button.callback(tr(ctx, 'cancel'), 'menu')]]));
  }
  if (s.step === 'memo') {
    s.order.memo = text;
    s.step = 'proof';
    userState.set(ctx.from.id, s);
    return ctx.reply(tr(ctx, 'sendProof'), Markup.inlineKeyboard([
      [Markup.button.callback(tr(ctx, 'skip'), 'skip_proof')],
      [Markup.button.callback(tr(ctx, 'cancel'), 'menu')],
    ]));
  }
  await ctx.reply(tr(ctx, 'menu'), mainKeyboard(ctx));
});

function escapeHtml(str) {
  return String(str)
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#039;');
}

app.get('/', (req, res) => res.send('Payment Assistant Site Bot is running ✅'));
app.get('/health', (req, res) => res.json({ ok: true, apiBase: CONFIG.API_BASE }));
app.get('/config', (req, res) => res.json({ site: CONFIG.SITE_URL, api: CONFIG.API_BASE }));

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
