const { Telegraf } = require('telegraf');
const { initDB, addUser, getUsersCount, getDbStatus } = require('./database');

const BOT_TOKEN = process.env.BOT_TOKEN;

if (!BOT_TOKEN) {
  throw new Error('BOT_TOKEN غير موجود داخل Railway Variables');
}

const bot = new Telegraf(BOT_TOKEN);

function hasSensitiveToken(text = '') {
  const patterns = [
    /accessToken/i,
    /sessionToken/i,
    /Bearer\s+/i,
    /__Secure-next-auth/i,
    /authsession/i,
    /eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}/,
    /eyJ[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{5,}\.[a-zA-Z0-9_-]{20,}\.[a-zA-Z0-9_-]{20,}/
  ];

  return patterns.some((regex) => regex.test(text));
}

function safeDecode(value) {
  let current = String(value || '').trim();
  for (let i = 0; i < 4; i += 1) {
    try {
      const decoded = decodeURIComponent(current);
      if (decoded === current) break;
      current = decoded;
    } catch (_) {
      break;
    }
  }
  return current;
}

function parseIncomingData(text) {
  const trimmed = String(text || '').trim();

  // يقبل JSON مباشر
  if (trimmed.startsWith('{') && trimmed.endsWith('}')) {
    return JSON.parse(trimmed);
  }

  // يقبل رابط يحتوي data= لكن بشرط يكون بدون توكنات حساسة
  let dataParam = null;
  try {
    const url = new URL(trimmed);
    dataParam = url.searchParams.get('data');
  } catch (_) {
    const match = trimmed.match(/[?&]data=([^&]+)/);
    dataParam = match ? match[1] : null;
  }

  if (!dataParam) {
    throw new Error('NO_JSON');
  }

  const decoded = safeDecode(dataParam);
  return JSON.parse(decoded);
}

function yesNo(value) {
  if (value === true) return 'نعم';
  if (value === false) return 'لا';
  return 'غير معروف';
}

function formatDate(value) {
  if (!value) return 'غير معروف';
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return String(value);
  return date.toISOString().slice(0, 10);
}

function formatAccount(data) {
  const user = data.user || {};
  const account = data.account || {};

  return [
    '✅ حالة الحساب',
    '',
    `👤 الاسم: ${user.name || 'غير معروف'}`,
    `📧 الإيميل: ${user.email || 'غير معروف'}`,
    '',
    `💳 نوع الخطة: ${account.planType || 'غير معروف'}`,
    `🏷️ نوع الحساب: ${account.structure || 'غير معروف'}`,
    `⚠️ متأخر بالدفع: ${yesNo(account.isDelinquent)}`,
    `🌍 المنطقة: ${account.residencyRegion || account.computeResidency || 'غير معروف'}`,
    `📅 انتهاء البيانات: ${formatDate(data.expires)}`,
    '',
    'ℹ️ حتى تحصل رابط الدفع الرسمي، افتح إعدادات الحساب من ChatGPT نفسه.'
  ].join('\n');
}

bot.start(async (ctx) => {
  const from = ctx.from || {};
  try {
    await addUser(from.id, from.username, from.first_name);
  } catch (_) {
    // قاعدة البيانات اختيارية، لا نوقف البوت إذا ما متصلة.
  }

  return ctx.reply(
    'أهلاً بيك ✅\n\n' +
    'أرسل بيانات الحساب بصيغة JSON منظفة أو رابط يحتوي data بدون accessToken وبدون sessionToken.\n\n' +
    'البوت راح يعرض حالة الحساب فقط بدون أزرار.'
  );
});

bot.command('debug', async (ctx) => {
  const db = getDbStatus();
  let count = 'غير متاح';
  try {
    count = String(await getUsersCount());
  } catch (_) {}

  return ctx.reply(
    '✅ البوت شغال\n' +
    '✅ BOT_TOKEN موجود\n' +
    `🗄️ قاعدة البيانات: ${db.ready ? 'متصلة' : 'غير متصلة'}\n` +
    `👥 عدد المستخدمين: ${count}\n` +
    `${db.error ? `⚠️ DB Error: ${db.error}` : ''}`
  );
});

bot.on('text', async (ctx) => {
  const text = ctx.message.text || '';

  if (hasSensitiveToken(text)) {
    return ctx.reply(
      '🚫 لا ترسل سيشن أو توكن داخل البوت.\n\n' +
      'accessToken و sessionToken مثل الباسورد، وأي رابط يحتويهن ممكن يفتح الحساب.\n' +
      'أرسل فقط JSON منظف بدون التوكنات حتى أعرض حالة الحساب.'
    );
  }

  try {
    const data = parseIncomingData(text);

    if (hasSensitiveToken(JSON.stringify(data))) {
      return ctx.reply(
        '🚫 البيانات تحتوي توكن/سيشن حساس. احذف accessToken و sessionToken وأرسل المعلومات العامة فقط.'
      );
    }

    if (!data.user && !data.account) {
      return ctx.reply('⚠️ البيانات وصلت، لكن ما بيها user أو account حتى أعرض الحالة.');
    }

    return ctx.reply(formatAccount(data));
  } catch (error) {
    return ctx.reply(
      'أرسل بيانات الحساب بصيغة JSON منظفة، مثل:\n\n' +
      '{\n' +
      '  "user": { "name": "Test", "email": "test@gmail.com" },\n' +
      '  "expires": "2026-07-24T14:50:34.105Z",\n' +
      '  "account": { "planType": "free", "structure": "personal", "isDelinquent": false }\n' +
      '}'
    );
  }
});

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));

(async () => {
  await initDB();
  await bot.launch();
  console.log('Bot is running ✅');
})();
