const puppeteer = require('puppeteer');

async function getScreenshot() {
    console.log('🚀 Launching browser...');
    // تشغيل المتصفح المخفي
    const browser = await puppeteer.launch({
        headless: true,
        args: ['--no-sandbox', '--disable-setuid-sandbox']
    });

    const page = await browser.newPage();
    // تمويه المتصفح حتى يبين كأنه مستخدم حقيقي
    await page.setUserAgent('Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36');

    try {
        console.log('🌐 Navigating to SheerID verification page...');
        await page.goto('https://services.sheerid.com/verify/67c8c14f5f17a83b745e3f82/', { waitUntil: 'networkidle0' });

        console.log('⏳ Waiting 5 seconds...');
        // انتظار 5 ثواني حتى تحمل الصفحة بالكامل
        await new Promise(r => setTimeout(r, 5000));

        console.log('📸 Taking screenshot...');
        // أخذ لقطة شاشة وحفظها بالذاكرة المؤقتة (Buffer)
        const screenshotBuffer = await page.screenshot({ fullPage: true });
        
        return screenshotBuffer;
    } catch (error) {
        console.error('❌ Error:', error);
        throw error;
    } finally {
        await browser.close();
    }
}

// تصدير الدالة حتى يستخدمها البوت
module.exports = { getScreenshot };
