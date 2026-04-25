const { Telegraf, Markup } = require('telegraf');
const axios = require('axios');
const { initDB, addUser, getUsersCount, getDbStatus, logFridaRun } = require('./database');
const { getAgents, runFridaScript } = require('./fridaClient');

const BOT_TOKEN = process.env.BOT_TOKEN;

if (!BOT_TOKEN) {
  console.error('❌ BOT_TOKEN غير موجود داخل Railway Variables');
  process.exit(1);
}

const bot = new Telegraf(BOT_TOKEN);

function mainMenu() {
  return Markup.inlineKeyboard([
    [Markup.button.callback('🛒 GoPlus', 'goplus')],
    [Markup.button.callback('🧪 Debug', 'debug')],
    [Markup.button.callback('📱 الأجهزة', 'devices')]
  ]);
}

function getPaymentConfig() {
  return {
    apiUrl: process.env.PAYMENT_API_URL || '',
    payloadJson: process.env.PAYMENT_PAYLOAD_JSON || '',
    apiKey: process.env.PAYMENT_API_KEY || ''
  };
}

async function registerUser(ctx) {
  try {
    const from = ctx.from || {};
    await addUser(from.id, from.username, from.first_name);
  } catch (error) {
    console.warn('⚠️ لم يتم حفظ المستخدم في قاعدة البيانات:', error.message);
  }
}

async function sendDebug(ctx) {
  const db = getDbStatus();
  let usersCountText = 'غير متاح';

  try {
    usersCountText = String(await getUsersCount());
  } catch (_) {}

  const agents = getAgents();
  const debugText = [
    '✅ البوت شغال',
    `BOT_TOKEN: ${BOT_TOKEN ? 'موجود ✅' : 'مفقود ❌'}`,
    `Database: ${db.ready ? 'متصلة ✅' : 'غير متصلة ❌'}`,
    db.error ? `DB Error: ${db.error}` : null,
    `Users Count: ${usersCountText}`,
    `FRIDA_AGENTS: ${Object.keys(agents).length ? Object.keys(agents).join(', ') : 'فارغ'}`,
    `PAYMENT_API_URL: ${process.env.PAYMENT_API_URL ? 'موجود ✅' : 'غير موجود'}`
  ].filter(Boolean).join('\n');

  return ctx.reply(debugText);
}

async function createPaymentLink(ctx) {
  const chatId = ctx.chat?.id;
  const { apiUrl, payloadJson, apiKey } = getPaymentConfig();

  if (!apiUrl || !payloadJson) {
    return ctx.reply(
      '⚠️ أمر GoPlus موجود، لكن إعدادات الدفع غير مكتملة.\n' +
      'أضف PAYMENT_API_URL و PAYMENT_PAYLOAD_JSON داخل Railway Variables.'
    );
  }

  let payload;
  try {
    payload = JSON.parse(payloadJson);
  } catch (error) {
    return ctx.reply('❌ PAYMENT_PAYLOAD_JSON مو JSON صحيح. صحّح المتغير داخل Railway.');
  }

  await ctx.reply('جاري إنشاء الرابط، انتظر لحظة...');

  try {
    const headers = { 'Content-Type': 'application/json' };
    if (apiKey) headers.Authorization = `Bearer ${apiKey}`;

    const response = await axios.post(apiUrl, payload, { headers, timeout: 30000 });
    const data = response.data || {};

    const paymentLink =
      data?.data?.payment_url ||
      data?.data?.paymentUrl ||
      data?.payment_url ||
      data?.paymentUrl ||
      data?.url ||
      data?.link;

    if (paymentLink) {
      return ctx.reply(`تم إنشاء الرابط بنجاح ✅\n\n${paymentLink}`);
    }

    return ctx.reply(`وصل رد من السيرفر لكن ما لقيت رابط دفع:\n${JSON.stringify(data).slice(0, 900)}`);
  } catch (error) {
    const msg = error.response
      ? `HTTP ${error.response.status}: ${JSON.stringify(error.response.data).slice(0, 500)}`
      : error.message;
    console.error('Payment API error:', msg);
    return ctx.reply(`عذراً، فشل الاتصال بنظام الدفع.\n${msg}`);
  }
}

bot.start(async (ctx) => {
  await registerUser(ctx);
  return ctx.reply(
    'أهلاً بك في CD Store! 🛒\nاختار من الأزرار أو اكتب /debug للفحص.',
    mainMenu()
  );
});

bot.command('debug', sendDebug);
bot.action('debug', async (ctx) => {
  await ctx.answerCbQuery();
  return sendDebug(ctx);
});

bot.command('goplus', createPaymentLink);
bot.action('goplus', async (ctx) => {
  await ctx.answerCbQuery();
  return createPaymentLink(ctx);
});

bot.command('devices', async (ctx) => {
  const agents = getAgents();
  const names = Object.keys(agents);
  if (!names.length) return ctx.reply('ماكو أجهزة مسجلة. أضف FRIDA_AGENTS داخل Railway.');
  return ctx.reply(`الأجهزة المسجلة:\n${names.map((name) => `• ${name}`).join('\n')}\n\nللتشغيل اكتب:\n/run_frida device_id`);
});

bot.action('devices', async (ctx) => {
  await ctx.answerCbQuery();
  const agents = getAgents();
  const names = Object.keys(agents);
  if (!names.length) return ctx.reply('ماكو أجهزة مسجلة. أضف FRIDA_AGENTS داخل Railway.');
  return ctx.reply(`الأجهزة المسجلة:\n${names.map((name) => `• ${name}`).join('\n')}\n\nللتشغيل اكتب:\n/run_frida device_id`);
});

bot.command('run_frida', async (ctx) => {
  const parts = (ctx.message?.text || '').trim().split(/\s+/);
  const deviceId = parts[1];

  if (!deviceId) {
    return ctx.reply('اكتب الجهاز بعد الأمر، مثال:\n/run_frida phone1');
  }

  await ctx.reply(`جاري التنفيذ على ${deviceId}...`);
  const result = await runFridaScript(deviceId, ctx.from.id);

  try {
    await logFridaRun(ctx.from.id, deviceId, result.startsWith('✅') ? 'success' : 'failed', result);
  } catch (error) {
    console.warn('⚠️ لم يتم حفظ سجل Frida:', error.message);
  }

  return ctx.reply(result);
});

bot.catch((err, ctx) => {
  console.error(`❌ Bot error for update ${ctx.update?.update_id}:`, err);
});

(async () => {
  await initDB();
  await bot.launch();
  console.log('✅ Telegram bot is running.');
})();

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
