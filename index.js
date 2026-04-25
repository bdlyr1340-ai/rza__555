const { Telegraf, Markup } = require('telegraf');
const axios = require('axios');
const { initDB } = require('./database');

const BOT_TOKEN = process.env.BOT_TOKEN;

if (!BOT_TOKEN) {
  console.error('❌ يرجى إضافة BOT_TOKEN في متغيرات Railway!');
  process.exit(1);
}

const bot = new Telegraf(BOT_TOKEN);

// ذاكرة مؤقتة لحفظ السيشن الخاص بكل مستخدم
const userSessions = new Map();

bot.start((ctx) => {
  const welcomeText = "أهلاً بك في البوت! 🛒\n\nللبدء، يرجى إرسال **السيشن (Session)** الخاص بك في رسالة نصية، وسأقوم بإنشاء رابط الدفع لك.";
  return ctx.reply(welcomeText);
});

// استقبال الرسائل النصية (التي نتوقع أن تكون هي السيشن)
bot.on('text', (ctx) => {
  const text = ctx.message.text.trim();

  // تجاهل الأوامر التي تبدأ بـ /
  if (text.startsWith('/')) return;

  // حفظ السيشن الخاص بهذا المستخدم (برقم الآي دي الخاص به)
  userSessions.set(ctx.from.id, text);

  // إرسال أزرار الخيارات
  return ctx.reply(
    "✅ تم استلام السيشن بنجاح!\n\nالآن، يرجى اختيار الباقة التي تريد إصدار رابط الدفع لها:",
    Markup.inlineKeyboard([
      [Markup.button.callback('Plus 🌟', 'plan_plus')],
      [Markup.button.callback('Go 🚀', 'plan_go')],
      [Markup.button.callback('Pro 👑', 'plan_pro')]
    ])
  );
});

// التعامل مع ضغطات الأزرار
bot.action(/plan_(.+)/, async (ctx) => {
  const planSelected = ctx.match[1]; // سيحمل القيمة: plus أو go أو pro
  const userId = ctx.from.id;
  const sessionData = userSessions.get(userId);

  // التأكد من أن المستخدم أرسل السيشن قبل الضغط
  if (!sessionData) {
    return ctx.reply("❌ لم أتمكن من العثور على السيشن الخاص بك. يرجى إرسال السيشن مرة أخرى.");
  }

  // إخفاء حالة التحميل من الزر
  await ctx.answerCbQuery();
  
  // إرسال رسالة انتظار
  const waitMsg = await ctx.reply(`⏳ جاري إنشاء رابط دفع لباقة **${planSelected.toUpperCase()}**...`);

  try {
    // بناء البيانات للإرسال للسيرفر باستخدام السيشن ونوع الباقة
    const payload = {
      "country": "US",
      "planType": planSelected, // plus, go, pro
      "isShortLink": 0,
      "token": {
        "WARNING_BANNER": "!!!!!!!!!!!!!!!!!!!! DO NOT SHARE... !!!!!!!!!!!!!!!!!!!!",
        "accessToken": sessionData, // وضعنا السيشن هنا
        "sessionToken": sessionData, // ووضعنا السيشن هنا لضمان عملها
        "user": {
          "id": `user-${userId}`,
          "name": ctx.from.first_name || "User",
          "email": "user@example.com"
        }
      }
    };

    const headers = {
      "Content-Type": "application/json",
      "Origin": "https://gpt.aide.freespaces.app",
      "Referer": "https://gpt.aide.freespaces.app/"
    };

    const api_url = "https://gpt.serve.freespaces.app/api/payment/link";
    const response = await axios.post(api_url, payload, { headers });
    const payment_data = response.data;

    // التحقق من نجاح العملية ووجود الرابط
    if (payment_data.code === 200 && payment_data.data) {
      const payment_link = payment_data.data.payment_url;
      const success_msg = `تم إنشاء رابط الدفع بنجاح! 🎉\n\n📦 الباقة: **${planSelected.toUpperCase()}**\n🔗 رابط الدفع:\n${payment_link}\n\nللدعم الفني: +9647728257333`;
      
      // تعديل رسالة الانتظار لتصبح رسالة النجاح
      return ctx.telegram.editMessageText(ctx.chat.id, waitMsg.message_id, undefined, success_msg);
    } else {
      return ctx.telegram.editMessageText(ctx.chat.id, waitMsg.message_id, undefined, `❌ فشل إنشاء الرابط. السيرفر يقول: ${payment_data.message || 'خطأ غير معروف'}`);
    }

  } catch (error) {
    console.error(error);
    return ctx.telegram.editMessageText(ctx.chat.id, waitMsg.message_id, undefined, "عذراً، حدث خطأ أثناء الاتصال بنظام الدفع. يرجى التأكد من صلاحية السيشن أو التواصل مع الدعم الفني.");
  }
});

// التقاط أي أخطاء مفاجئة لكي لا يتوقف البوت عن العمل
bot.catch((err, ctx) => {
  console.error(`❌ Bot error for update ${ctx.update?.update_id}:`, err);
});

// تشغيل البوت وقاعدة البيانات
(async () => {
  await initDB();
  await bot.launch();
  console.log('✅ Telegram bot is running.');
})();

// إيقاف آمن
process.once('SIGINT', () => bot.stop('SIGINT'));
process.once('SIGTERM', () => bot.stop('SIGTERM'));
