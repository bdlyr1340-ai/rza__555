require('dotenv').config();
const TelegramBot = require('node-telegram-bot-api');
// استدعاء ملف التصوير
const { getScreenshot } = require('./services/scraper');

// جلب التوكن من متغيرات البيئة في Railway
const token = process.env.TELEGRAM_BOT_TOKEN;

// تشغيل البوت
const bot = new TelegramBot(token, { polling: true });

console.log('🤖 Bot is running...');

// الرد على أمر البدء
bot.onText(/\/start/, (msg) => {
    const chatId = msg.chat.id;
    bot.sendMessage(chatId, 'أهلاً بيك! دزلي أمر /screenshot حتى أجيبلك لقطة من الموقع.');
});

// الرد على أمر سحب الصورة
bot.onText(/\/screenshot/, async (msg) => {
    const chatId = msg.chat.id;
    
    bot.sendMessage(chatId, '⏳ ثواني، دأفتح الموقع وأسحب الصورة...');

    try {
        // تشغيل كود التصوير
        const imageBuffer = await getScreenshot();
        // إرسال الصورة للمستخدم
        await bot.sendPhoto(chatId, imageBuffer, { caption: '📸 تفضل، هذي لقطة الشاشة من الموقع!' });
    } catch (error) {
        bot.sendMessage(chatId, '❌ صارت مشكلة وما كدرت أسحب الصورة. تأكد من إعدادات السيرفر.');
    }
});
