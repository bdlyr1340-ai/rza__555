require('dotenv').config();
const axios = require('axios');
const crypto = require('crypto');
const fs = require('fs');
const path = require('path');

// ==========================================
// الإعدادات البيئية (Environment Variables)
// ==========================================
const MAIL_DOMAIN = process.env.MAIL_DOMAIN || "";
const MAIL_WORKER_BASE = (process.env.MAIL_WORKER_BASE || "").replace(/\/$/, "");
const MAIL_ADMIN_PASSWORD = process.env.MAIL_ADMIN_PASSWORD || "";
const TOKEN_OUTPUT_DIR = (process.env.TOKEN_OUTPUT_DIR || "").trim();
const CLI_PROXY_AUTHS_DIR = (process.env.CLI_PROXY_AUTHS_DIR || "").trim();

const AUTH_URL = "https://auth.openai.com/oauth/authorize";
const TOKEN_URL = "https://auth.openai.com/oauth/token";
const CLIENT_ID = "app_EMoamEEZ73f0CkXaXp7hrann";
const DEFAULT_REDIRECT_URI = "http://localhost:1455/auth/callback";
const DEFAULT_SCOPE = "openid email profile offline_access";

// ==========================================
// دوال مساعدة (Helpers & Crypto)
// ==========================================
function randomString(length) {
    const chars = 'abcdefghijklmnopqrstuvwxyz0123456789';
    let result = '';
    for (let i = 0; i < length; i++) {
        result += chars.charAt(Math.floor(Math.random() * chars.length));
    }
    return result;
}

function getEmailAndToken() {
    const prefix = randomString(10);
    const email = `${prefix}@${MAIL_DOMAIN}`;
    return { email, token: email };
}

function base64UrlEncode(buffer) {
    return buffer.toString('base64')
        .replace(/\+/g, '-')
        .replace(/\//g, '_')
        .replace(/=/g, '');
}

function sha256Base64Url(str) {
    const hash = crypto.createHash('sha256').update(str).digest();
    return base64UrlEncode(hash);
}

function randomState(bytes = 16) {
    return base64UrlEncode(crypto.randomBytes(bytes));
}

function pkceVerifier() {
    return base64UrlEncode(crypto.randomBytes(32)); // 64 in original, but 32 bytes = 43 chars base64
}

function generatePassword(length = 16) {
    const chars = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789!@#$%&*';
    let pass = '';
    for (let i = 0; i < length; i++) pass += chars.charAt(Math.floor(Math.random() * chars.length));
    return pass;
}

function generateOAuthUrl(redirectUri = DEFAULT_REDIRECT_URI, scope = DEFAULT_SCOPE) {
    const state = randomState();
    const codeVerifier = pkceVerifier();
    const codeChallenge = sha256Base64Url(codeVerifier);

    const params = new URLSearchParams({
        client_id: CLIENT_ID,
        response_type: "code",
        redirect_uri: redirectUri,
        scope: scope,
        state: state,
        code_challenge: codeChallenge,
        code_challenge_method: "S256",
        prompt: "login",
        id_token_add_organizations: "true",
        codex_cli_simplified_flow: "true"
    });

    return {
        authUrl: `${AUTH_URL}?${params.toString()}`,
        state,
        codeVerifier,
        redirectUri
    };
}

const sleep = (ms) => new Promise(resolve => setTimeout(resolve, ms));

// ==========================================
// استخراج الكود البريدي (OTP)
// ==========================================
function extractOtpCode(content) {
    if (!content) return "";
    const patterns = [
        /Your ChatGPT code is\s*(\d{6})/i,
        /ChatGPT code is\s*(\d{6})/i,
        /verification code to continue:\s*(\d{6})/i,
        /Subject:.*?(\d{6})/i,
        /(?<!\d)(\d{6})(?!\d)/
    ];

    for (const pattern of patterns) {
        const match = content.match(pattern);
        if (match) return match[1];
    }
    return "";
}

async function getOaiCode(email, seenIds = new Set()) {
    process.stdout.write(`[*] 正在等待邮箱 ${email} 的验证码...`);
    const headers = {
        "x-admin-auth": MAIL_ADMIN_PASSWORD,
        "Content-Type": "application/json"
    };

    for (let i = 0; i < 40; i++) {
        process.stdout.write(".");
        try {
            const res = await axios.get(`${MAIL_WORKER_BASE}/admin/mails`, {
                params: { limit: 5, offset: 0, address: email },
                headers,
                timeout: 15000
            });

            const results = res.data.results || [];
            for (const mail of results) {
                if (seenIds.has(mail.id)) continue;
                seenIds.add(mail.id);
                
                const raw = mail.raw || "";
                let content = raw;
                const subjMatch = raw.match(/^Subject:\s*(.+)$/m);
                if (subjMatch) content = subjMatch[1] + "\n" + raw;

                const code = extractOtpCode(content);
                if (code) {
                    console.log(` 抓到啦! 验证码: ${code}`);
                    return code;
                }
            }
        } catch (error) {
            // تجاهل الأخطاء والمحاولة مرة أخرى
        }
        await sleep(3000);
    }
    console.log(" 超时，未收到验证码");
    return "";
}

// ==========================================
// عملية التسجيل الأساسية (Registration Flow)
// ==========================================
async function run() {
    const { email, token } = getEmailAndToken();
    if (!email) return null;
    
    console.log(`[*] 成功获取临时邮箱与授权: ${email}`);
    const oauth = generateOAuthUrl();
    const password = generatePassword();
    
    // إعداد الـ Client للاتصال (Axios instance)
    const client = axios.create({
        timeout: 15000,
        headers: {
            "accept": "application/json",
            "content-type": "application/json",
        }
    });

    try {
        // الخطوة 1: الحصول على صفحة الـ Auth
        const authResp = await client.get(oauth.authUrl, { maxRedirects: 0, validateStatus: () => true });
        const cookies = authResp.headers['set-cookie'] || [];
        let did = "";
        cookies.forEach(c => {
            if (c.includes('oai-did=')) did = c.split('oai-did=')[1].split(';')[0];
        });

        // الخطوة 2: تجاوز الـ Sentinel
        console.log(`[*] Device ID: ${did}`);
        const senToken = "dummy-token-placeholder"; // ملاحظة: هنا ستحتاج لتطبيق منطق Sentinel الكامل إذا لزم الأمر
        const sentinelHeader = JSON.stringify({ p: "", t: "", c: senToken, id: did, flow: "authorize_continue" });

        // الخطوة 3: إرسال طلب إنشاء الحساب
        const signupResp = await client.post("https://auth.openai.com/api/accounts/authorize/continue", 
            { username: { value: email, kind: "email" }, screen_hint: "signup" },
            { headers: { "openai-sentinel-token": sentinelHeader } }
        );

        if (signupResp.status === 403) {
            console.log("[Error] 403 Forbidden - قد تحتاج لاستخدام مكتبة تتخطى حماية Cloudflare مثل TLS-Client");
            return null;
        }

        // الخطوة 4: إدخال الرقم السري
        const pwdResp = await client.post("https://auth.openai.com/api/accounts/user/register", 
            { username: email, password: password },
            { headers: { "openai-sentinel-token": sentinelHeader } }
        );

        console.log(`[*] 提交注册(密码)状态: ${pwdResp.status}`);

        // الخطوة 5: جلب كود التفعيل (OTP)
        console.log("[*] 需要邮箱验证，开始等待验证码...");
        const code = await getOaiCode(email);
        if (!code) return null;

        // الخطوة 6: تفعيل الكود
        const codeResp = await client.post("https://auth.openai.com/api/accounts/email-otp/validate", 
            { code: code },
            { headers: { "openai-sentinel-token": sentinelHeader } }
        );
        console.log(`[*] 验证码校验状态: ${codeResp.status}`);

        // إنشاء البيانات الوهمية
        const names = ["Smith", "John", "David", "Ali", "Omar", "Sara"];
        const randomName = names[Math.floor(Math.random() * names.length)];
        const userInfo = { name: randomName, birthdate: "2000-01-01" };

        // إتمام إنشاء الحساب
        const createAccResp = await client.post("https://auth.openai.com/api/accounts/create_account", userInfo);
        console.log(`[*] 账户创建状态: ${createAccResp.status}`);
        
        return { email, password };

    } catch (error) {
        console.log(`[Error] 运行时发生错误: ${error.message}`);
        return null;
    }
}

// ==========================================
// نقطة تشغيل البوت الرئيسية (Main)
// ==========================================
async function main() {
    console.log("[Info] Node.js OpenAI Auto-Registrar Started");
    console.log("=".repeat(60));

    let count = 0;
    while (true) {
        count++;
        console.log(`\n[${new Date().toLocaleTimeString()}] >>> 开始第 ${count} 次注册流程 <<<`);
        
        const account = await run();
        
        if (account) {
            console.log(`[*] 成功! الحساب: ${account.email} | الباسورد: ${account.password}`);
            const accountLine = `${account.email}----${account.password}\n`;
            
            // حفظ الحساب في ملف
            fs.appendFileSync('accounts.txt', accountLine, 'utf8');
            console.log("[*] 账号密码已追加至: accounts.txt");
        } else {
            console.log("[-] 本次注册失败。");
        }

        // إيقاف مؤقت عشوائي بين 5 و 15 ثانية لتجنب الحظر السريع
        const waitTime = Math.floor(Math.random() * (15000 - 5000 + 1)) + 5000;
        console.log(`[*] 休息 ${waitTime / 1000} 秒...`);
        await sleep(waitTime);
    }
}

// تشغيل السكربت
main();
