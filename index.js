require('dotenv').config();
const { Telegraf, Markup } = require('telegraf');
const { initDB, addUser, logFridaRun } = require('./database');
const { runFridaScript } = require('./fridaClient');

const bot = new Telegraf(process.env.BOT_TOKEN);

// دالة للحصول على قائمة الأجهزة
function getDevicesList() {
  try {
    const agents = JSON.parse(process.env.FRIDA_AGENTS || '{}');
    return Object.keys(agents);
  } catch {
    return [];
  }
}

// لوحة التحكم الرئيسية
function mainMenu() {
  return Markup.inlineKeyboard([
    [Markup.button.callback('📱 عرض الأجهزة', 'show_devices')],
    [Markup.button.callback('🚀 تشغيل Frida', 'run_frida_menu')],
    [Markup.button.callback('📊 عدد المستخدمين', 'users_count')]
  ]);
}

// زر رجوع
function backButton() {
  return Markup.inlineKeyboard([Markup.button.callback('🔙 رجوع', 'main_menu')]);
}

bot.start(async (ctx) => {
  const user = ctx.from;
  await addUser(user.id, user.username, user.first_name);
  await ctx.reply('🔧 لوحة تحكم البوت:', mainMenu());
});

bot.action('main_menu', async (ctx) => {
  await ctx.editMessageText('🔧 لوحة تحكم البوت:', mainMenu());
});

bot.action('show_devices', async (ctx) => {
  const devices = getDevicesList();
  if (!devices.length) {
    await ctx.editMessageText('❌ لا توجد أجهزة مسجلة.', backButton());
    return;
  }
  const buttons = devices.map(d => [Markup.button.callback(`📱 ${d}`, `select_${d}`)]);
  buttons.push([Markup.button.callback('🔙 رجوع', 'main_menu')]);
  await ctx.editMessageText('📱 الأجهزة المتاحة:', Markup.inlineKeyboard(buttons));
});

bot.action('run_frida_menu', async (ctx) => {
  const devices = getDevicesList();
  if (!devices.length) {
    await ctx.editMessageText('❌ لا توجد أجهزة. أضفها في متغير FRIDA_AGENTS.', backButton());
    return;
  }
  const buttons = devices.map(d => [Markup.button.callback(`▶️ ${d}`, `run_${d}`)]);
  buttons.push([Markup.button.callback('🔙 رجوع', 'main_menu')]);
  await ctx.editMessageText('اختر جهازاً لتشغيل السكريبت:', Markup.inlineKeyboard(buttons));
});

bot.action('users_count', async (ctx) => {
  try {
    const { rows } = await require('./database').pool.query('SELECT COUNT(*) FROM users');
    const count = rows[0].count;
    await ctx.editMessageText(`👥 عدد المستخدمين: ${count}`, backButton());
  } catch (err) {
    await ctx.editMessageText('خطأ في جلب العدد', backButton());
  }
});

// معالج اختيار جهاز للعرض
bot.action(/^select_(.*)/, async (ctx) => {
  const device = ctx.match[1];
  const agents = JSON.parse(process.env.FRIDA_AGENTS || '{}');
  const url = agents[device];
  await ctx.editMessageText(`📱 الجهاز: ${device}\n🌐 العنوان: ${url}`, backButton());
});

// تشغيل Frida على جهاز
bot.action(/^run_(.*)/, async (ctx) => {
  const device = ctx.match[1];
  const userId = ctx.from.id;
  await ctx.editMessageText(`⏳ جاري تشغيل السكريبت على ${device} ...`);
  const result = await runFridaScript(device, userId);
  const status = result.startsWith('✅') ? 'success' : 'failed';
  await logFridaRun(userId, device, status, result);
  await ctx.reply(result, backButton());
});

// بدء البوت
async function main() {
  await initDB();
  console.log('✅ قاعدة البيانات جاهزة');
  await bot.launch();
  console.log('🚀 البوت يعمل...');
}

main();
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));