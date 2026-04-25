const { Telegraf, Markup } = require('telegraf');
const axios = require('axios');
const { initDB } = require('./database');

// سحب التوكن من Railway
const BOT_TOKEN = process.env.BOT_TOKEN;

if (!BOT_TOKEN) {
  console.error('❌ يرجى إضافة BOT_TOKEN في متغيرات Railway!');
  process.exit(1);
}

const bot = new Telegraf(BOT_TOKEN);

// ذاكرة لحفظ السيشن اللي راح ترسله
const userSessions = new Map();

bot.start((ctx) => {
  return ctx.reply("أهلاً بك! 🛒\n\nيرجى إرسال **السيشن (Session)** الخاص بك في رسالة، وسأقوم بإنشاء الرابط لك.");
});

// استقبال السيشن من المستخدم
bot.on('text', (ctx) => {
  const text = ctx.message.text.trim();
  
  // تجاهل الأوامر مثل /start
  if (text.startsWith('/')) return;

  // التأكد من أن السيشن طويل وغير منقوص
  if (text.length < 50) {
      return ctx.reply("❌ السيشن قصير جداً! يرجى التأكد من نسخه بالكامل وإرساله.");
  }

  // حفظ السيشن مؤقتاً
  userSessions.set(ctx.from.id, text);
  
  // إظهار خيارات الخدمات
  return ctx.reply(
    "✅ تم استلام السيشن بنجاح!\n\nاختر نوع الخدمة التي تريدها:",
    Markup.inlineKeyboard([
      [Markup.button.callback('خدمة Plus 🌟', 'plan_plus')],
      [Markup.button.callback('خدمة Go 🚀', 'plan_goplus')]
    ])
  );
});

// التعامل مع ضغطات الأزرار (Plus أو Go)
bot.action(/plan_(.+)/, async (ctx) => {
  const planSelected = ctx.match[1]; // القيمة راح تكون plus أو goplus
  const userId = ctx.from.id;
  const sessionData = userSessions.get(userId);

  if (!sessionData) {
    return ctx.reply("❌ لم أجد السيشن الخاص بك. يرجى إرساله مرة أخرى.");
  }

  await ctx.answerCbQuery();
  const planName = planSelected === 'goplus' ? 'Go' : 'Plus';
  const waitMsg = await ctx.reply(`⏳ جاري طلب رابط خدمة **${planName}**...`);

  try {
    // بناء الطلب باستخدام السيشن المرسل والبيانات الأصلية التي يقبلها السيرفر
    const payload = {
      "country": "US",
      "planType": planSelected,
      "isShortLink": 0,
      "token": {
        "WARNING_BANNER": "!!!!!!!!!!!!!!!!!!!! DO NOT SHARE ANY PART OF THE INFORMATION YOU SEE HERE. THIS INFORMATION IS SENSITIVE AND CAN GRANT ACCESS TO YOUR ACCOUNT. SHARING THIS INFORMATION IS LIKE SHARING YOUR PASSWORD. !!!!!!!!!!!!!!!!!!!!",
        "accessToken": sessionData, // وضع السيشن اللي دزيته هنا
        "account": {
          "id": "c7a43504-f61c-4d0b-9c6b-e85afe02ec4b",
          "planType": "free",
          "structure": "personal"
        },
        "authProvider": "openai",
        "expires": "2026-07-24T14:50:34.105Z",
        "rumViewTags": { "light_account": { "fetched": false } },
        "sessionToken": sessionData, // وضع السيشن هنا أيضاً
        "user": {
          "id": "user-jh9ztkwmi181aTyMZPj8FpFx", // نفس بيانات الحساب التي يقبلها السيرفر
          "name": "YouTube Premium",
          "email": "hnshalshayb69@gmail.com"
        }
      }
    };

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

    if (payment_link && payment_link.length > 5) {
      const success_msg = `تم إنشاء الرابط بنجاح! 🎉\n\n📦 الخدمة: **${planName}**\n🔗 رابط الدفع:\n${payment_link}\n\nللدعم الفني: +9647728257333`;
      return ctx.telegram.editMessageText(ctx.chat.id, waitMsg.message_id, undefined, success_msg);
    } else {
      // في حال رد السيرفر بنجاح لكن بدون رابط (بسبب سيشن مستخدم أو خطأ من السيرفر)
      return ctx.telegram.editMessageText(
        ctx.chat.id, 
        waitMsg.message_id, 
        undefined, 
        `❌ السيرفر قبل الطلب لكنه لم يرجع رابط الدفع!\n\nالسبب المحتمل: السيشن مستخدم مسبقاً أو غير صالح لهذه الباقة.\nرد السيرفر: ${data.message}`
      );
    }

  } catch (error) {
    let errorMsg = error.message;
    if (error.response) {
        errorMsg = `الرمز: ${error.response.status}`;
    }
    return ctx.telegram.editMessageText(ctx.chat.id, waitMsg.message_id, undefined, `🔌 فشل الاتصال بالسيرفر: ${errorMsg}`);
  }
});

// منع توقف البوت في حال الأخطاء
bot.catch((err, ctx) => {
  console.error(`❌ Bot error:`, err);
});

// التشغيل
(async () => {
  await initDB();
  await bot.launch();
  console.log('✅ Telegram bot is running.');
})();

// الإيقاف الآمن
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
