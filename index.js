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
  
  if (text.startsWith('/')) return;

  if (text.length < 20) {
      return ctx.reply("❌ السيشن خطأ! يبدو غير صالح أو لم تقم بنسخه بالكامل. يرجى التأكد وإعادة الإرسال.");
  }

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
  let planSelected = ctx.match[1]; // plus, go, pro
  const userId = ctx.from.id;
  const sessionData = userSessions.get(userId);

  if (!sessionData) return ctx.reply("❌ أعد إرسال السيشن أولاً.");

  await ctx.answerCbQuery();
  const waitMsg = await ctx.reply(`⏳ جاري طلب رابط **${planSelected.toUpperCase()}**...`);

  // تصحيح اسم الباقة ليطابق السيرفر (حسب كودك القديم كان اسمها goplus)
  let apiPlanType = planSelected;
  if (planSelected === 'go') apiPlanType = 'goplus';

  try {
    const payload = {
      "country": "US",
      "planType": apiPlanType,
      "isShortLink": 0,
      "token": {
        "accessToken": sessionData,
        "sessionToken": sessionData,
        // إضافة بيانات المستخدم لأن بعض السيرفرات لا تولد الرابط بدونها
        "user": {
          "id": `user-${userId}`,
          "name": ctx.from.first_name || "User",
          "email": "user@example.com"
        },
        "account": {
          "id": "c7a43504-f61c-4d0b-9c6b-e85afe02ec4b",
          "planType": "free",
          "structure": "personal"
        }
      }
    };

    // إضافة Headers الأصلية لمنع السيرفر من رفض الطلب
    const headers = {
      "Content-Type": "application/json",
      "Origin": "https://gpt.aide.freespaces.app",
      "Referer": "https://gpt.aide.freespaces.app/"
    };

    const api_url = "https://gpt.serve.freespaces.app/api/payment/link";
    const response = await axios.post(api_url, payload, { 
        headers: headers,
        timeout: 15000 
    });

    const data = response.data;
    
    // استخراج الرابط
    const payment_link = 
      data?.data?.payment_url || 
      data?.data?.paymentUrl || 
      data?.payment_url || 
      data?.url || 
      data?.link;

    // التأكد من أن الرابط ليس فارغاً (أطول من 5 أحرف مثلاً)
    if (payment_link && payment_link.length > 5) {
      const success_msg = `تم إنشاء الرابط بنجاح! 🎉\n\n📦 الباقة: **${planSelected.toUpperCase()}**\n🔗 الرابط:\n${payment_link}\n\nللدعم: +9647728257333`;
      return ctx.telegram.editMessageText(ctx.chat.id, waitMsg.message_id, undefined, success_msg);
    } else {
      const errorDetail = JSON.stringify(data, null, 2);
      return ctx.telegram.editMessageText(
        ctx.chat.id, 
        waitMsg.message_id, 
        undefined, 
        `❌ السيرفر رد بنجاح لكنه لم يرسل الرابط!\n\nتفاصيل الرد:\n\`\`\`json\n${errorDetail}\n\`\`\``,
        { parse_mode: 'Markdown' }
      );
    }

  } catch (error) {
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

bot.catch((err, ctx) => {
  console.error(`❌ Bot error:`, err);
});

(async () => {
  await initDB();
  await bot.launch();
  console.log('✅ Bot is running.');
})();
