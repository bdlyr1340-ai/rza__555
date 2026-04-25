const { Telegraf, Markup } = require('telegraf');
const axios = require('axios');
const { initDB } = require('./database');

const BOT_TOKEN = process.env.BOT_TOKEN;

if (!BOT_TOKEN) {
  console.error('❌ يرجى إضافة BOT_TOKEN في متغيرات Railway!');
  process.exit(1);
}

const bot = new Telegraf(BOT_TOKEN);
const userSessions = new Map();

bot.start((ctx) => {
  return ctx.reply("أهلاً بك! 🛒\n\nيرجى إرسال **السيشن (Session)** الخاص بك الآن.");
});

bot.on('text', (ctx) => {
  const text = ctx.message.text.trim();
  
  // تجاهل الأوامر
  if (text.startsWith('/')) return;

  // 1. فحص السيشن إذا كان خطأ أو ناقص
  // السيشن عادة يكون نص طويل جداً، فإذا كان أقل من 20 حرفاً نعتبره خطأ
  if (text.length < 20) {
      return ctx.reply("❌ السيشن خطأ! يبدو غير صالح أو لم تقم بنسخه بالكامل. يرجى التأكد وإعادة الإرسال.");
  }

  // 2. السيشن صحيح
  userSessions.set(ctx.from.id, text);
  return ctx.reply(
    "✅ السيشن صحيح! ماذا تختار؟",
    Markup.inlineKeyboard([
      [Markup.button.callback('Plus 🌟', 'plan_plus')],
      [Markup.button.callback('Go 🚀', 'plan_go')],
      [Markup.button.callback('Pro 👑', 'plan_pro')]
    ])
  );
});

bot.action(/plan_(.+)/, async (ctx) => {
  const planSelected = ctx.match[1];
  const userId = ctx.from.id;
  const sessionData = userSessions.get(userId);

  if (!sessionData) return ctx.reply("❌ أعد إرسال السيشن أولاً.");

  await ctx.answerCbQuery();
  const waitMsg = await ctx.reply(`⏳ جاري طلب رابط **${planSelected.toUpperCase()}**...`);

  try {
    const payload = {
      "country": "US",
      "planType": planSelected,
      "isShortLink": 0,
      "token": {
        "accessToken": sessionData,
        "sessionToken": sessionData
      }
    };

    const api_url = "https://gpt.serve.freespaces.app/api/payment/link";
    const response = await axios.post(api_url, payload, { 
        headers: { "Content-Type": "application/json" },
        timeout: 15000 
    });

    const data = response.data;
    
    // البحث عن الرابط في الرد
    const payment_link = 
      data?.data?.payment_url || 
      data?.data?.paymentUrl || 
      data?.payment_url || 
      data?.url || 
      data?.link;

    if (payment_link) {
      const success_msg = `تم إنشاء الرابط بنجاح! 🎉\n\n📦 الباقة: **${planSelected.toUpperCase()}**\n🔗 الرابط:\n${payment_link}\n\nللدعم: +9647728257333`;
      return ctx.telegram.editMessageText(ctx.chat.id, waitMsg.message_id, undefined, success_msg);
    } else {
      // 3. عرض المشكلة الحقيقية من السيرفر إذا لم يظهر الرابط
      const errorDetail = JSON.stringify(data, null, 2);
      return ctx.telegram.editMessageText(
        ctx.chat.id, 
        waitMsg.message_id, 
        undefined, 
        `❌ لم يتم العثور على رابط دفع.\n\nتفاصيل الرد من السيرفر لمعرفة المشكلة:\n\`\`\`json\n${errorDetail}\n\`\`\``,
        { parse_mode: 'Markdown' }
      );
    }

  } catch (error) {
    // عرض خطأ الاتصال بالسيرفر بالتفصيل
    let errorMsg = error.message;
    if (error.response) {
        errorMsg = `الرمز: ${error.response.status}\nالرد: ${JSON.stringify(error.response.data, null, 2)}`;
    }
    return ctx.telegram.editMessageText(
        ctx.chat.id, 
        waitMsg.message_id, 
        undefined, 
        `🔌 فشل الاتصال بالسيرفر!\n\nتفاصيل الخطأ:\n\`\`\`\n${errorMsg}\n\`\`\``,
        { parse_mode: 'Markdown' }
    );
  }
});

// منع توقف البوت في حال حدوث خطأ مفاجئ
bot.catch((err, ctx) => {
  console.error(`❌ Bot error:`, err);
});

(async () => {
  await initDB();
  await bot.launch();
  console.log('✅ Bot is running.');
})();
