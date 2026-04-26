const TelegramBot = require('node-telegram-bot-api');
const { exec } = require('child_process');
const fs = require('fs');
const path = require('path');

// ================== التهيئة ==================
require('dotenv').config();

const BOT_TOKEN = process.env.BOT_TOKEN;          // توكن البوت
const PROXY = process.env.PROXY || '';            // بروكسي افتراضي
const PYTHON_SCRIPT = 'script.py';                // اسم ملف السكريبت الخاص بك

// متغيرات البيئة التي يحتاجها السكريبت (من ملف .env)
const MAIL_DOMAIN = process.env.MAIL_DOMAIN;
const MAIL_WORKER_BASE = process.env.MAIL_WORKER_BASE;
const MAIL_ADMIN_PASSWORD = process.env.MAIL_ADMIN_PASSWORD;
const TOKEN_OUTPUT_DIR = process.env.TOKEN_OUTPUT_DIR || './tokens';
const CLI_PROXY_AUTHS_DIR = process.env.CLI_PROXY_AUTHS_DIR || './auths';

// تأكد من وجود مجلد الإخراج
if (!fs.existsSync(TOKEN_OUTPUT_DIR)) fs.mkdirSync(TOKEN_OUTPUT_DIR, { recursive: true });
if (CLI_PROXY_AUTHS_DIR && !fs.existsSync(CLI_PROXY_AUTHS_DIR)) fs.mkdirSync(CLI_PROXY_AUTHS_DIR, { recursive: true });

// ================== إنشاء البوت ==================
const bot = new TelegramBot(BOT_TOKEN, { polling: true });

// حالة المستخدم لتخزين البروكسي الخاص به
const userSessions = {};

// ================== لوحة المفاتيح الرئيسية ==================
const mainMenu = {
  reply_markup: {
    inline_keyboard: [
      [{ text: '🔄 تسجيل حساب جديد', callback_data: 'register' }],
      [{ text: '📊 فحص التوكنات', callback_data: 'check_tokens' }],
      [{ text: '🌐 تعيين البروكسي', callback_data: 'set_proxy' }],
      [{ text: '🆘 مساعدة', callback_data: 'help' }]
    ]
  }
};

// ================== تشغيل السكريبت ==================
function runPythonScript(proxy, userId) {
  return new Promise((resolve, reject) => {
    // تحضير متغيرات البيئة للعملية الفرعية
    const env = {
      ...process.env,
      MAIL_DOMAIN,
      MAIL_WORKER_BASE,
      MAIL_ADMIN_PASSWORD,
      TOKEN_OUTPUT_DIR,
      CLI_PROXY_AUTHS_DIR
    };

    const proxyArg = proxy ? `--proxy "${proxy}"` : '';
    const command = `python3 ${PYTHON_SCRIPT} --once ${proxyArg}`;

    console.log(`[userId:${userId}] تشغيل: ${command}`);
    exec(command, { env, cwd: __dirname }, (error, stdout, stderr) => {
      if (error) {
        console.error(`[userId:${userId}] خطأ:`, stderr);
        return reject(stderr || error.message);
      }
      resolve(stdout);
    });
  });
}

// ================== معالجة الأوامر الأساسية ==================
bot.onText(/\/start/, (msg) => {
  bot.sendMessage(msg.chat.id,
    `🤖 *بوت التسجيل التلقائي لـ OpenAI*\n` +
    `الرجاء استخدام الأزرار أدناه للتحكم.`,
    { parse_mode: 'Markdown', ...mainMenu }
  );
});

// ================== استقبال الأزرار ==================
bot.on('callback_query', async (callbackQuery) => {
  const chatId = callbackQuery.message.chat.id;
  const userId = callbackQuery.from.id;
  const data = callbackQuery.data;

  // استخدام البروكسي الخاص بالمستخدم إذا وجد
  const userProxy = userSessions[userId] || PROXY;

  switch (data) {
    case 'register': {
      const msg = await bot.sendMessage(chatId, '⏳ جارٍ بدء التسجيل...');
      try {
        const output = await runPythonScript(userProxy, userId);

        // محاولة استخراج اسم ملف التوكن المحفوظ من المخرجات
        const tokenFileMatch = output.match(/Token 已保存至: (.+)$/m);
        const copyMatch = output.match(/Token 已拷贝至: (.+)$/m);
        const successMatch = output.match(/成功! Token 已保存至: (.+)$/m);

        const tokenPath = tokenFileMatch?.[1] || copyMatch?.[1] || successMatch?.[1];

        if (tokenPath && fs.existsSync(tokenPath)) {
          const tokenContent = fs.readFileSync(tokenPath, 'utf-8');
          await bot.editMessageText(
            `✅ تم التسجيل بنجاح!\n\n` +
            `الملف: \`${path.basename(tokenPath)}\`\n` +
            `المحتوى:\n\`\`\`json\n${tokenContent.substring(0, 300)}...\n\`\`\``,
            { chat_id: chatId, message_id: msg.message_id, parse_mode: 'Markdown' }
          );
          // إرسال الملف كملف مرفق
          await bot.sendDocument(chatId, tokenPath, {}, { filename: path.basename(tokenPath) });
        } else {
          await bot.editMessageText(
            `⚠️ تم تشغيل السكريبت ولكن لم يتم العثور على ملف التوكن.\n\nالمخرجات:\n\`\`\`\n${output.substring(0, 1000)}\n\`\`\``,
            { chat_id: chatId, message_id: msg.message_id, parse_mode: 'Markdown' }
          );
        }
      } catch (err) {
        await bot.editMessageText(
          `❌ فشل التسجيل:\n\`\`\`\n${err.substring(0, 1000)}\n\`\`\``,
          { chat_id: chatId, message_id: msg.message_id, parse_mode: 'Markdown' }
        );
      }
      break;
    }

    case 'check_tokens': {
      let statsText = '';
      try {
        const output = await runPythonScript(userProxy, userId, ['--check']);
        const lines = output.split('\n');
        const summaryLines = lines.filter(l => l.includes('共') || l.includes('有效') || l.includes('删除'));
        statsText = summaryLines.join('\n');
      } catch (e) {
        statsText = 'فشل في تشغيل الفحص';
      }

      // إحصاء سريع من المجلد
      if (fs.existsSync(CLI_PROXY_AUTHS_DIR)) {
        const files = fs.readdirSync(CLI_PROXY_AUTHS_DIR).filter(f => f.startsWith('codex-'));
        statsText += `\n\n📂 عدد ملفات التوكن في المجلد: ${files.length}`;
      }

      await bot.sendMessage(chatId, `📊 *حالة التوكنات*\n${statsText}`, { parse_mode: 'Markdown', ...mainMenu });
      break;
    }

    case 'set_proxy': {
      // طلب إدخال البروكسي
      await bot.sendMessage(chatId, '🌐 الرجاء إرسال البروكسي بالصيغة: `http://user:pass@ip:port`', { parse_mode: 'Markdown' });
      // ننتظر رد المستخدم
      bot.once('message', (msg) => {
        if (msg.chat.id === chatId && msg.text && msg.text.startsWith('http')) {
          userSessions[userId] = msg.text.trim();
          bot.sendMessage(chatId, `✅ تم تعيين البروكسي: \`${msg.text.trim()}\``, { parse_mode: 'Markdown' });
        } else {
          bot.sendMessage(chatId, '❌ صيغة غير صحيحة');
        }
      });
      break;
    }

    case 'help': {
      await bot.sendMessage(chatId,
        `📖 *كيفية الاستخدام*\n` +
        `- استخدم زر "تسجيل حساب جديد" لبدء عملية تسجيل.\n` +
        `- بعد التسجيل الناجح سيتم إرسال ملف JSON.\n` +
        `- يمكنك فحص التوكنات لمعرفة عدد الصالح منها.\n` +
        `- لتعيين بروكسي مختلف، استخدم زر "تعيين البروكسي".`,
        { parse_mode: 'Markdown', ...mainMenu }
      );
      break;
    }
  }

  // تأكيد استلام الكول باك
  await bot.answerCallbackQuery(callbackQuery.id);
});

console.log('✅ البوت يعمل...');
