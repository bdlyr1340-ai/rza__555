const { Telegraf, Markup } = require('telegraf');
const axios = require('axios');
const { initDB } = require('./database');

const BOT_TOKEN = process.env.BOT_TOKEN;
const PAYMENT_API_KEY = process.env.PAYMENT_API_KEY;

if (!BOT_TOKEN) {
  console.error('❌ يرجى إضافة BOT_TOKEN في متغيرات Railway!');
  process.exit(1);
}

const bot = new Telegraf(BOT_TOKEN);
const userSessions = new Map();

bot.start((ctx) => {
  return ctx.reply("أهلاً بك! 🛒\n\nيرجى إرسال **السيشن (Session)** الخاص بك في رسالة.");
});

bot.on('text', (ctx) => {
  const text = ctx.message.text.trim();
  
  if (text.startsWith('/')) return;

  if (text.length < 50) {
      return ctx.reply("❌ السيشن قصير جداً! يرجى التأكد من نسخه بالكامل.");
  }

  // 🟢 التعديل الأهم: قراءة السيشن بشكل صحيح
  // إذا دزيت السيشن كملف JSON كامل، البوت راح يحلله بشكل صحيح
  let parsedSession;
  try {
    parsedSession = JSON.parse(text);
  } catch (e) {
    // وإذا دزيته كنص عادي (JWT)، راح يعتبره نص
    parsedSession = text; 
  }

  userSessions.set(ctx.from.id, parsedSession);
  
  return ctx.reply(
    "✅ تم استلام السيشن بنجاح!\n\nاختر نوع الخدمة التي تريدها:",
    Markup.inlineKeyboard([
      [Markup.button.callback('خدمة Plus 🌟', 'plan_plus')],
      [Markup.button.callback('خدمة Go 🚀', 'plan_goplus')]
    ])
  );
});

bot.action(/plan_(.+)/, async (ctx) => {
  const planSelected = ctx.match[1];
  const userId = ctx.from.id;
  const sessionData = userSessions.get(userId);

  if (!sessionData) return ctx.reply("❌ أعد إرسال السيشن أولاً.");

  await ctx.answerCbQuery();
  const planName = planSelected === 'goplus' ? 'Go' : 'Plus';
  const waitMsg = await ctx.reply(`⏳ جاري طلب رابط خدمة **${planName}**...`);

  try {
    // 🟢 ترتيب الطلب حسب نوع السيشن اللي دزيته
    let tokenPayload;
    if (typeof sessionData === 'object') {
        // إذا السيشن مالتك JSON، راح نرسله مثل ما هو بالضبط وبدون تخريب
        tokenPayload = sessionData;
    } else {
        // إذا السيشن مالتك مجرد كود نصي، راح نبني له الهيكل الصحيح
        tokenPayload = {
          "accessToken": sessionData,
          "sessionToken": sessionData,
          "user": {
            "id": `user-${userId}`,
            "name": "YouTube Premium",
            "email": "hnshalshayb69@gmail.com"
          },
          "account": {
            "id": "c7a43504-f61c-4d0b-9c6b-e85afe02ec4b",
            "planType": "free",
            "structure": "personal"
          }
        };
    }

    const payload = {
      "country": "US",
      "planType": planSelected,
      "isShortLink": 0,
      "token": tokenPayload // تم تركيب السيشن بشكل سليم
    };

    const headers = {
      "Content-Type": "application/json",
      "Origin": "https://gpt.aide.freespaces.app",
      "Referer": "https://gpt.aide.freespaces.app/"
    };

    if (PAYMENT_API_KEY) {
        headers["Authorization"] = `Bearer ${PAYMENT_API_KEY}`;
    }

    const api_url = "https://gpt.serve.freespaces.app/api/payment/link";
    const response = await axios.post(api_url, payload, { headers, timeout: 15000 });
    const data = response.data;
    
    const payment_link = data?.data?.payment_url || data?.data?.paymentUrl || data?.payment_url || data?.url || data?.link;

    if (payment_link && payment_link.length > 5) {
      const success_msg = `تم إنشاء الرابط بنجاح! 🎉\n\n📦 الخدمة: **${planName}**\n🔗 رابط الدفع:\n${payment_link}\n\nللدعم الفني: +9647728257333`;
      return ctx.telegram.editMessageText(ctx.chat.id, waitMsg.message_id, undefined, success_msg);
    } else {
      return ctx.telegram.editMessageText(
        ctx.chat.id, waitMsg.message_id, undefined, 
        `❌ السيرفر قبل الطلب لكنه لم يرجع رابط الدفع!\n\nرد السيرفر: ${data.message}`
      );
    }
  } catch (error) {
    let errorMsg = error.message;
    if (error.response) {
        errorMsg = `الرمز: ${error.response.status}\nالرد: ${JSON.stringify(error.response.data).slice(0,100)}`;
    }
    return ctx.telegram.editMessageText(ctx.chat.id, waitMsg.message_id, undefined, `🔌 فشل الاتصال بالسيرفر: ${errorMsg}`);
  }
});

bot.catch((err) => console.error(`❌ Bot error:`, err));

(async () => {
  await initDB();
  await bot.launch();
  console.log('✅ Telegram bot is running.');
})();

process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
