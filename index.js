const { Telegraf, Markup } = require('telegraf');
const { initDB, addUser, getUsersCount, logFridaRun } = require('./database');
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
    [Markup.button.callback('📊 عدد المستخدمين', 'users_count')]
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
    await ctx.editMessageText(text, mainKeyboard());
  } else {
    await ctx.reply(text, mainKeyboard());
  }
}

bot.start(async (ctx) => {
  const user = ctx.from;
  await addUser(user.id, user.username, user.first_name);
  await showMainMenu(ctx);
});

bot.action('main_menu', async (ctx) => {
  await ctx.answerCbQuery();
  await showMainMenu(ctx, '🔧 لوحة التحكم:');
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
  const count = await getUsersCount();
  return ctx.editMessageText(`👥 المستخدمون: ${count}`, backKeyboard());
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

  await logFridaRun(userId, device, status, result);
  return ctx.reply(result, backKeyboard());
});

bot.catch((err, ctx) => {
  console.error('Bot error:', err);
  if (ctx) ctx.reply('❌ صار خطأ بالبوت. راجع Logs في Railway.').catch(() => {});
});

(async () => {
  await initDB();
  await bot.launch();
  console.log('✅ Bot is running...');
})();

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
