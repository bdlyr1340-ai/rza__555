const { Telegraf, Markup } = require('telegraf');
const { initDB, addUser, getUsersCount, logFridaRun, getDbStatus } = require('./database');
const { getAgents, runFridaScript } = require('./fridaClient');

const BOT_TOKEN = process.env.BOT_TOKEN;

if (!BOT_TOKEN) {
  console.error('❌ BOT_TOKEN غير موجود في Variables داخل Railway');
  process.exit(1);
}

const bot = new Telegraf(BOT_TOKEN);

function mainKeyboard() {
  return Markup.inlineKeyboard([
    [Markup.button.callback('📱 عرض الأجهزة', 'show_devices')],
    [Markup.button.callback('🚀 تشغيل Frida', 'run_frida_menu')],
    [Markup.button.callback('📊 عدد المستخدمين', 'users_count')],
    [Markup.button.callback('🧪 فحص الإعدادات', 'diagnostics')]
  ]);
}

function backKeyboard() {
  return Markup.inlineKeyboard([
    [Markup.button.callback('🔙 رجوع', 'main_menu')]
  ]);
}

function devicesKeyboard(prefix) {
  const devices = Object.keys(getAgents());
  const rows = devices.map((device) => [
    Markup.button.callback(`📱 ${device}`, `${prefix}:${device}`)
  ]);
  rows.push([Markup.button.callback('🔙 رجوع', 'main_menu')]);
  return Markup.inlineKeyboard(rows);
}

async function showMainMenu(ctx, text = '🔧 لوحة تحكم البوت:') {
  if (ctx.callbackQuery) {
    return ctx.editMessageText(text, mainKeyboard());
  }
  return ctx.reply(text, mainKeyboard());
}

bot.start(async (ctx) => {
  try {
    const user = ctx.from;
    await addUser(user.id, user.username, user.first_name);
  } catch (err) {
    console.error('⚠️ addUser failed, but menu will still open:', err.message);
  }
  await showMainMenu(ctx);
});

bot.command('debug', async (ctx) => {
  const db = getDbStatus();
  const devices = Object.keys(getAgents());
  await ctx.reply(
    `🧪 Debug\n` +
    `BOT_TOKEN: ✅ موجود\n` +
    `Database: ${db.ready ? '✅ متصلة' : '❌ غير متصلة'}\n` +
    `DB Error: ${db.error || 'لا يوجد'}\n` +
    `FRIDA_AGENTS devices: ${devices.length ? devices.join(', ') : '❌ لا توجد'}\n`,
    backKeyboard()
  );
});

bot.action('main_menu', async (ctx) => {
  await ctx.answerCbQuery();
  await showMainMenu(ctx, '🔧 لوحة التحكم:');
});

bot.action('diagnostics', async (ctx) => {
  await ctx.answerCbQuery();
  const db = getDbStatus();
  const devices = Object.keys(getAgents());
  return ctx.editMessageText(
    `🧪 فحص الإعدادات\n\n` +
    `BOT_TOKEN: ✅ موجود\n` +
    `Database: ${db.ready ? '✅ متصلة' : '❌ غير متصلة'}\n` +
    `DB Error: ${db.error || 'لا يوجد'}\n` +
    `FRIDA_AGENTS: ${devices.length ? '✅ ' + devices.join(', ') : '❌ فارغ أو JSON خطأ'}`,
    backKeyboard()
  );
});

bot.action('show_devices', async (ctx) => {
  await ctx.answerCbQuery();
  const devices = Object.keys(getAgents());

  if (!devices.length) {
    return ctx.editMessageText('❌ لا توجد أجهزة. تأكد من متغير FRIDA_AGENTS في Railway.', backKeyboard());
  }

  return ctx.editMessageText('📱 الأجهزة:', devicesKeyboard('select'));
});

bot.action('run_frida_menu', async (ctx) => {
  await ctx.answerCbQuery();
  const devices = Object.keys(getAgents());

  if (!devices.length) {
    return ctx.editMessageText('❌ لا توجد أجهزة. تأكد من متغير FRIDA_AGENTS في Railway.', backKeyboard());
  }

  return ctx.editMessageText('اختر جهازاً:', devicesKeyboard('run'));
});

bot.action('users_count', async (ctx) => {
  await ctx.answerCbQuery();
  try {
    const count = await getUsersCount();
    return ctx.editMessageText(`👥 المستخدمون: ${count}`, backKeyboard());
  } catch (err) {
    console.error('❌ users_count error:', err);
    return ctx.editMessageText(`❌ قاعدة البيانات غير متصلة.\n\nالسبب: ${err.message}`, backKeyboard());
  }
});

bot.action(/^select:(.+)$/, async (ctx) => {
  await ctx.answerCbQuery();
  const device = ctx.match[1];
  const url = getAgents()[device] || 'غير معروف';
  return ctx.editMessageText(`📱 الجهاز: ${device}\n🔗 العنوان: ${url}`, backKeyboard());
});

bot.action(/^run:(.+)$/, async (ctx) => {
  await ctx.answerCbQuery();
  const device = ctx.match[1];
  const userId = ctx.from.id;

  await ctx.editMessageText(`⏳ جاري التشغيل على ${device}...`);
  const result = await runFridaScript(device, userId);
  const status = result.startsWith('✅') ? 'success' : 'failed';

  try {
    await logFridaRun(userId, device, status, result);
  } catch (err) {
    console.error('⚠️ logFridaRun failed:', err.message);
  }

  return ctx.reply(result, backKeyboard());
});

bot.catch((err, ctx) => {
  console.error('❌ Bot error full:', err);
  const msg = `❌ صار خطأ بالبوت:\n${err.message || String(err)}\n\nاكتب /debug حتى تشوف فحص الإعدادات.`;
  if (ctx) ctx.reply(msg).catch(() => {});
});

(async () => {
  await initDB();
  await bot.launch();
  console.log('✅ Bot is running...');
})();

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
