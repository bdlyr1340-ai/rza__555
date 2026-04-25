const { Telegraf, Markup } = require('telegraf');
const axios = require('axios');
const { initDB } = require('./database');

const BOT_TOKEN = process.env.BOT_TOKEN;

if (!BOT_TOKEN) {
  console.error('❌ يرجى إضافة BOT_TOKEN!');
  process.exit(1);
}

const bot = new Telegraf(BOT_TOKEN);
const userSessions = new Map();

bot.start((ctx) => {
  return ctx.reply("أهلاً بك! 🛒\n\nيرجى نسخ **كود السيشن الكامل (JSON)** من الموقع وإرساله هنا.");
});

bot.on('text', (ctx) => {
  const text = ctx.message.text.trim();
  if (text.startsWith('/')) return;

  let tokenObj;
  try {
    // هنا البوت راح يستقبل الملف الكامل اللي نسخته من الموقع بدون ما يغير حرف
    tokenObj = JSON.parse(text);
  } catch (e) {
    return ctx.reply("❌ السيشن اللي دزيته مو بصيغة صحيحة. لازم تنسخ الكود الكامل اللي يبدأ بقوس { وبيه بيانات الحساب.");
  }

  userSessions.set(ctx.from.id, tokenObj);
  
  return ctx.reply(
    "✅ تم استلام السيشن بشكل صحيح ومطابق للموقع!\n\nاختر الخدمة اللي تريد تولد رابط إلها:",
    Markup.inlineKeyboard([
      [Markup.button.callback('خدمة Plus 🌟', 'plan_plus')],
      [Markup.button.callback('خدمة Go 🚀', 'plan_goplus')]
    ])
  );
});

bot.action(/plan_(.+)/, async (ctx) => {
  const planSelected = ctx.match[1];
  const userId = ctx.from.id;
  const tokenObj = userSessions.get(userId);

  if (!tokenObj) return ctx.reply("❌ أعد إرسال السيشن أولاً.");

  await ctx.answerCbQuery();
  const planName = planSelected === 'goplus' ? 'Go' : 'Plus';
  const waitMsg = await ctx.reply(`⏳ جاري طلب رابط خدمة **${planName}** من الموقع...`);

  try {
    // نركب الطلب ونخلي السيشن مالتك مثل ما هو بالضبط
    const payload = {
      "country": "US",
      "planType": planSelected,
      "isShortLink": 0,
      "token": tokenObj 
    };

    const headers = {
      "Content-Type": "application/json",
      "Origin": "https://gpt.aide.freespaces.app",
      "Referer": "https://gpt.aide.freespaces.app/"
    };

    // إذا عندك API KEY خليه بمتغيرات Railway، إذا ما عندك البوت راح يشتغل بدونه
    if (process.env.PAYMENT_API_KEY) {
        headers["Authorization"] = `Bearer ${process.env.PAYMENT_API_KEY}`;
    }

    const api_url = "https://gpt.serve.freespaces.app/api/payment/link";
    const response = await axios.post(api_url, payload, { headers, timeout: 15000 });
    const data = response.data;
    
    const payment_link = data?.data?.payment_url || data?.data?.paymentUrl || data?.payment_url || data?.url || data?.link;

    if (payment_link && payment_link.length > 5) {
      return ctx.telegram.editMessageText(
        ctx.chat.id, waitMsg.message_id, undefined, 
        `تم إنشاء الرابط بنجاح! 🎉\n\n📦 الخدمة: **${planName}**\n🔗 رابط الدفع:\n${payment_link}`
      );
    } else {
      return ctx.telegram.editMessageText(
        ctx.chat.id, waitMsg.message_id, undefined, 
        `❌ السيرفر قبل الطلب بس ما رجع رابط!\nرد السيرفر: ${data.message}`
      );
    }
  } catch (error) {
    let errorMsg = error.message;
    if (error.response) errorMsg = `الرمز: ${error.response.status}\nالرد: ${JSON.stringify(error.response.data).slice(0,100)}`;
    return ctx.telegram.editMessageText(ctx.chat.id, waitMsg.message_id, undefined, `🔌 فشل الاتصال: ${errorMsg}`);
  }
});

bot.catch((err) => console.error(`❌ Bot error:`, err));

(async () => {
  await initDB();
  await bot.launch();
})();
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
