const { Telegraf } = require('telegraf');
const axios = require('axios');
const { initDB } = require('./database');

// سحب توكن البوت من متغيرات البيئة في Railway
const BOT_TOKEN = process.env.BOT_TOKEN;

// التأكد من أن التوكن موجود حتى لا يتوقف الكود فجأة
if (!BOT_TOKEN) {
  console.error('❌ يرجى إضافة BOT_TOKEN في متغيرات Railway!');
  process.exit(1);
}

const bot = new Telegraf(BOT_TOKEN);

bot.start((ctx) => {
  const welcomeText = "أهلاً بك في CD Store! 🛒\nلإصدار رابط دفع لاشتراك GoPlus، أرسل الأمر:\n/goplus";
  return ctx.reply(welcomeText);
});

bot.command('goplus', async (ctx) => {
  await ctx.reply("جاري إنشاء رابط الدفع المخصص لك، يرجى الانتظار...");

  try {
    const payload = {
      "country": "US",
      "planType": "goplus",
      "isShortLink": 0,
      "token": {
        "WARNING_BANNER": "!!!!!!!!!!!!!!!!!!!! DO NOT SHARE ANY PART OF THE INFORMATION YOU SEE HERE. THIS INFORMATION IS SENSITIVE AND CAN GRANT ACCESS TO YOUR ACCOUNT. SHARING THIS INFORMATION IS LIKE SHARING YOUR PASSWORD. !!!!!!!!!!!!!!!!!!!!",
        "accessToken": "eyJhbGciOiJSUzI1NiIsImtpZCI6IjE5MzQ0ZTY1LWJiYzktNDRkMS1hOWQwLWY5NTdiMDc5YmQwZSIsInR5cCI6IkpXVCJ9.eyJhdWQiOlsiaHR0cHM6Ly9hcGkub3BlbmFpLmNvbS92MSJdLCJjbGllbnRfaWQiOiJhcHBfWDh6WTZ2VzJwUTl0UjNkRTduSzFqTDVnSCIsImV4cCI6MTc3Nzg1ODEyNiwiaHR0cHM6Ly9hcGkub3BlbmFpLmNvbS9hdXRoIjp7ImNoYXRncHRfYWNjb3VudF9pZCI6ImM3YTQzNTA0LWY2MWMtNGQwYi05YzZiLWU4NWFmZTAyZWM0YiIsImNoYXRncHRfYWNjb3VudF91c2VyX2lkIjoidXNlci1qaDl6dGt3bWkxODFhVHlNWlBqOEZwRnhfX2M3YTQzNTA0LWY2MWMtNGQwYi05YzZiLWU4NWFmZTAyZWM0YiIsImNoYXRncHRfY29tcHV0ZV9yZXNpZGVuY3kiOiJub19jb25zdHJhaW50IiwiY2hhdGdwdF9wbGFuX3R5cGUiOiJmcmVlIiwiY2hhdGdwdF91c2VyX2lkIjoidXNlci1qaDl6dGt3bWkxODFhVHlNWlBqOEZwRngiLCJ1c2VyX2lkIjoidXNlci1qaDl6dGt3bWkxODFhVHlNWlBqOEZwRngifSwiaHR0cHM6Ly9hcGkub3BlbmFpLmNvbS9wcm9maWxlIjp7ImVtYWlsIjoiaG5zaGFsc2hheWI2OUBnbWFpbC5jb20iLCJlbWFpbF92ZXJpZmllZCI6dHJ1ZX0sImlhdCI6MTc3Njk5NDEyNSwiaXNzIjoiaHR0cHM6Ly9hdXRoLm9wZW5haS5jb20iLCJqdGkiOiJjOTRkNjYzMi0yNTE1LTQ3NDAtYTRkOC0xNWNhMzBhMjc1ZjEiLCJuYmYiOjE3NzY5OTQxMjUsInB3ZF9hdXRoX3RpbWUiOjE3NzY5OTQxMjQyMzksInNjcCI6WyJvcGVuaWQiLCJlbWFpbCIsInByb2ZpbGUiLCJvZmZsaW5lX2FjY2VzcyIsIm1vZGVsLnJlcXVlc3QiLCJtb2RlbC5yZWFkIiwib3JnYW5pemF0aW9uLnJlYWQiLCJvcmdhbml6YXRpb24ud3JpdGUiXSwic2Vzc2lvbl9pZCI6ImF1dGhzZXNzXzdheTRKMGFTMkY0YUF0UTM3djNaNHVlaCIsInNsIjp0cnVlLCJzdWIiOiJnb29nbGUtb2F1dGgyfDEwMjA3MDE0Mjk4OTE3OTUzMjc4MCJ9.okZDD4hd8zr4dRp9JE7GVCUWfEhlWJ0NFu3yTZ1BWg1trBkukLCfxgab5s1carDGmoDxE99eFb_b7bqxkb6kNpa9gjKKSDL-kT3FcK9KRhtG22WgR39JZLmp4DzvukRwRXvVoBdJaXQv9RG5cK0Myq4mSCLScTXgTjjPg89juLLZpicc7Q2fGEP-nw5yTXPAHhtSaWS1sa_izQyxS61YPTVKLqYUy_3-4p41R9wJUcDJsFj7qMKF5w2IHeB-e-VyWBVYMJfThppSrxhayYF5gkAdUT7nWh4-WHkjz7dDQCckF8extxAlYdqZ8Z3PlKcpZKVPGKphg3xLtBWfl5vl4llJ3hentmCHni7vQZMiJqHTg0SCEJHcPCnUgsNaRPJrnvPGlioaKG6a2php5vt13hHX8yx1LzNZf-wlX0887TnVwULExXpZ6pQEWSDxFOyRmuYsCsTViwYniduTlFyP76ABcbptd1h-PVl0vLm5n9DaEl_dQRhVxwBXaaiudTugDKBuRpKYZEIHt9sXphpknRY3J9Pdauwd32UOt-MdDiUEDAoNb1E-pwwf0KrkKqeQ5ZZUfjYPGXUvw5ngkW0ICackxnpEpxPkCRCjumF-QZIknB4Pprb88kLF74U4753JLu0JCyg8v6q0Q7g8YwIKKhGanWLE7Xl2OpPQ18nmCjQ",
        "account": {
          "id": "c7a43504-f61c-4d0b-9c6b-e85afe02ec4b",
          "planType": "free",
          "structure": "personal"
        },
        "authProvider": "openai",
        "expires": "2026-07-24T14:50:34.105Z",
        "rumViewTags": { "light_account": { "fetched": false } },
        "sessionToken": "eyJhbGciOiJkaXIiLCJlbmMiOiJBMjU2R0NNIn0..YDq32xx7HgD3IHJf.iVAqM3411hagOzAXUyx-nLo4NVE_rg5NUS4Z_794BxrUdIc94qtrpU1ud5mmMUem1amWZcV5c1AfA5AFpY8DRXc6BpV_7gkf51SVBQGwm32OHYGVow-65iopOGNiGVQqehIo5-_WFTiIFM8c_73BLhIXsMvyaMBD_GkcCZncHstUE2AiUNbPYz1ajWPvfDQuHxkVKoyPC1W2I1R8lcPakYLOSThFQfBpmS2NUZfMkep1AzGw3Lp1hUuq5v8iK6FnP6XgUEoLxBKybNdYbzNx24GkP_OC1SS4s50Sgt2tjUtednovLzgKPhj-GisCkFbiUhBUcPJKtbPaY0cGBr0It-YC5oDEthEDwsjKtm1D1W4194uC4h64B1yCEWf_9OGD6-_xj3zhUZEVULTqblaf3bEiCdqkwAUmikEZTRNVCnTEe-6_KjzyP2ubj5WYa6cBGqaosTxdJco5cayUySVNBOjBPd9R0bN6MaTSBq_YxSxLD-EcHnuWNC8_Q8Y0MTinWgrSU5pjKDXJW4mjMXTn23VtH-CsUOI8DEb8sC6to68M22QjtloVjZO5wjHRmM0Bu7kBQP2NbCKuaz-UwIZ4g6Ub7QSpiXSY_h2_VUOH-YgsYY34eNyi5FEiiJAxiS9fFdtZyIyXepks27tJNbhq1RFo4yecvHmrp__7IaMKzch0TqxbqZ2CmtTH42APh0Ll4Qxa_VN6np4G49Yed5EPXaGiF0Ys4QXgsPZsf9C8cEwEnV5qtGg3KEiQMvolhFREofJZFPLdyXn0bI3p9TVzUlh4y9D22vYpXt3cI42ailG4xFuDnEWgg6goJph_DfbI_NcqGKvXkitMFw4pVTq8k4WhynINeivuPAW-6qAvS7NB7akgDjrj-v0HfyBtst5Oev8DXdNa2Pn6LGe4Qm0sM-gIIoUEsqfTBze8x8Dkdu6x0zHXof1M4P8z-R9WJ7SeGnW7MrgIB-WS8dJTpfz9yHUZ946JzLOHYhYlQ7PrcwfPmFoQYGoD1ouvXF2vWl7gYjLWdPLTp8bh-INip02Kv1WXMLbQdTLb4fmiOGEWotTxAqx1J5OE2ARy9PezHNuCu0e_Jaxk19LmCZVVZZJXRDWHThGwxr_4zPe9ENFAaCpSCq538eziF4pntr0pnEZxVAV3_ld-O7KambbyS5ris4h1RE3Q8XK2hqjYcy9pYupJVGlBjewVR_w8Tw7hoZDCq1CITcW5tuimrU1lfB-QVHPNnVC4X5HMEmM9RETIm81NCG_JTOKO3Txj0_cwFDnZoFvRigKRK1qzZKHDkwc1RPvrVInkdGROsJl65-Ca6oiRcnQauyrAeq3MUU7C3HeZn7K1fiVI81YYtLTy0VGI2bAca0c2lTbvr58Vs_i1Zmwjrs4aEEIqSOMtUKxIKvWSfMG6Tn-8pksB4FZtg5RkGzY6tKGi0w53nCMu66ZxqB-W1rwm03vXmnjIHRDQs7cmCkWdXXmTY1HJwk88LTAtav9yghfUIrJeeyjFizmX9J8ynvbXl1-9fyTpa3c6hZUIwXCUXB71doRs9zQzx1DHFH_GxXAzUvwg1l_Ez6SvFBeXV1NMHkfR0FTQrOuhoW-AjYv4hagiAloVq0skSFtPwS-uvgvuNjKiaqxxCd0z8gPRA2_Wm3Zv46KXGmjIaq-MlNV303OrNaaBdJGoT3hRG0PX3R1SafheCU2auPTD0kBHcHeTmCwGNByl8r2uJOXvkOwT4l7AoZW6h6vU7lIDlTmO5SpYHQQidqR3ID3JkcNxRVWASYyhwjfgNHBXld4Wxge7AvB6YVJfmg_LdU2m9uFshKlvvHhKSLJH8lSozcL8DITdqh5LL0ZNMHD9-RVRWcncrHZYCSa4bhXZFvpEfI7UKYaMJc_wPYzmoFzmamnktClD5cK7WasxZyn8vFs6d_9mXwva_f-LHbDvsNQO2bSwsMh5ZzQ5wcXV1LY5psifXl6Bccgx8xTUQpJP34cHIWOH4-hbF1yXLTsIZVTWRDgLPFyns1s3uPG9wSa4CvC3CrqwO_spmpY9KSPj4MF2CJ4U-Zk9GQTAXJ0Vr1r07VupS7gS0RabuyJltrk_sAJ_PziogId4I9UEc3lftYRyHi6D4GYRPXWN-C6pXj4bvLovmoUcktEPC454XsqBVinVnmuwml0oIwvvH-04fENvbRW_h4A5_5KHJpTUbzbmK1MXqZXcoVuxdDW8s4tOrUXvlxRfjt8q_kId7AOAanh0_bvI2ly1L8hs2DQQxiQBI5ZvdL-E9RHL5kTfpulK9NJJi-B-bmqjScvdEajSv88A4uWr8tAXx8uvvYs5gK-gQmNJ2gJ-85T03fH9RBjkvrXVemSgKIszLV64gLIEJMha16LBFnUV_ywEPHsTVrUDrBhVWWUqc1VntyXC0r_IYunaE5X5MW2T1FNtFrSTX7lpF330Rzqd7iJrmc4OSlOmRbNEm7c9ixbtztt0DKJgnssi6PXeW7wUeSZ0LQKfbKVUQmqmEyCr3stkzfXSb0bqrsjINE2V0KG5IZOHOYvs_sWQ309FEV9cf7qkAD7O9VlXkImZjWEPMB6zXE65DG7vatbtxNeV3Ys9aJNl39APS-0SkFJHZpvH7fgAL1lHnTyZVUc8Z4fbkfvnzilfrJO59-BxhMHJWx0zBPCJ4l2t0J0Pu4eKIsErRg-ck92piEpOmGpX_Yj4QrkCuWLDVbUiUTSQfZ9w-RZgsCffevqutlHcnaodGiBM_jGlScnF6r7-bjme7dQHZMjOIN4GTxYxd9p7ybHL8y6seTO202UxUszaYdzJkPNmp_D-IBh3-temwOD8W_ZoHmCLhja8v8UENXxE9P7ld5YROWdrr7IDAHt-3ByXYNhhYYVztw6bzQaClbU27AbZngk7z1KUNe3Bndza9VkLTffjvz7O2zmgcT3dTeGqdcaS7K_ln8aKfMxO4G5SFhfLqTu9QNiO582iPl0S1UjvGHN7CzABTWVd7vQbQTkNf8api5moSRieLTWFhAaFpzZxkh1ZgqZ5mXOZ0EHaDHG0lv-m1j5iwwAq7DmN_EWHTlMmNbT-8VdC4RsLYRuXllXz9lKjdaZ943YrOwlrRneXGLbeRPIZTniX5TU6CgAlFdFqcNts_uujfcjmtD1ei1SOF5KtJR7yERbEtYyG2dECq01Adggv7afxHSqGJlnmjAggZkJKDsa6yesU1oqtPfn5GM2xWjox9eRHWxQck3SLt9lLksZpqnZNkCYfOh0v6v0cFEYDYj8rO9VPabFnhs7jLG3SNplfwGIBTqqCLmwc-PuFYF0WP-3kivSYgWG81-Qzh5izrIvxzdfK290dFs334fglT4nnKTrGq3kRBAo7LWWEMDMgScLikDAbVZWAXdUY2Qc5x7JVlNzfEzxLjC1AAfybQ6QblRCuvSWflsdT4BOBKCuLDk_A7Qv7py4iS8bpc6FEhAllO3iaMipLewbTDRuXvsFIy0qo4HJvXOzhc2SGZYcL128Wx6SrMMWlpqm6hEYF4Qk6PFGqMLadwhdFyh4oZvpHeEBmkkfBohYjtFCKM4A1iJdKEvuMmNY1gfEUgG9mtt2UTXVzAw11iIeFreBnjTlgU6U2JOaZO1CPmqJbgDywQZJiIpsY_dv0WCirOgMjTdiob_OTKLB36NRqC5iQBkOWwtvAryPbhoS4WaS-tAEMrf6tNlumQQUe_PERocPUJuAloS9nowiWrG8fdL7BdYNk1FIkyvS6wmTelW8taDaHznX0YKi5wtrSY_0qd9nBg7IFjTCAkbgjlIY2lpPhY05uECP1rBySqWnESIHltp23FUjS_Z2YUMDI1HTmzxL5YL6Go2BRKMz14yrDJsRHSJ52dPxaIH8r1ZZXvp_PdcVU5GrKM59GKneA_ErTVC30WgkLVRi1w_S6txwv-CiPfCG7mDQLmizIFjZc24ra_7ZQH-MJPNn0CuUHowYjzfI0WPTHS-fv1_P6kyxVyefLiUYobavX4LG-L5VfstYgyV725ekC146gUDoRMqvUhwGtb3Rmc1bIh2NakW18U0RLV6U7ca3IQqbCTGCVx9JBnm2FZ-JiGDkj0QkWHxcbdZ9t9vrMeL3EePdmy_NlafT_6QUSd6Ne-FadbJYSAVvfv-RJ9xrcW7Vq5B0annJgrWtf6zeZyWD5Zv9F_iPFrJ3DwlwR_yZrJOpUsw.P8hDV75OjMA8PZMgLGlrrA",
        "user": {
          "id": "user-jh9ztkwmi181aTyMZPj8FpFx",
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
    const response = await axios.post(api_url, payload, { headers });
    const payment_data = response.data;

    if (payment_data.code === 200 && payment_data.data) {
      const payment_link = payment_data.data.payment_url;
      const success_msg = `تم إنشاء رابط الدفع بنجاح! 🎉\n\nاضغط هنا للدفع:\n${payment_link}\n\nللدعم الفني: +9647728257333`;
      return ctx.reply(success_msg);
    } else {
      return ctx.reply(`فشل إنشاء الرابط. السيرفر يقول: ${payment_data.message}`);
    }

  } catch (error) {
    console.error(error);
    return ctx.reply("عذراً، حدث خطأ أثناء الاتصال بنظام الدفع. يرجى التواصل مع الدعم الفني: +9647728257333");
  }
});

// التعامل مع الأخطاء لكي لا يتوقف البوت
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
