/**
 * hook_1m.js — ChatGPT Plus 1 month free trial
 */

"use strict";

var OFFER_TOKEN = "ATCTYGUcx/4WvKJhyWqP44PKT+OR3BE5bx9loRE13nkb9gEac4+LBPrHs3dxGcmDZcLcDeYwl5pqFF1Mx7eVuJScrMow2C0BVyn/2XKDBMiiZW/rGQ4wp6ZhAK5eRLlv2dpoCIbIwqDtfyZoK6E=";

var _keepAlive = setInterval(function() {}, 1000);
function log(msg) { console.log("[1M] " + msg); }

(function() {
    var mod = Process.findModuleByName("libpairipcore.so");
    if (!mod) return;
    Process.enumerateRanges("r-x").forEach(function(r) {
        if (r.base.compare(mod.base) < 0 ||
            r.base.compare(mod.base.add(mod.size)) >= 0) return;
        try {
            Memory.protect(r.base, r.size, "rwx");
            var buf = new Uint8Array(r.size);
            buf.fill(0xC3);
            Memory.writeByteArray(r.base, buf.buffer);
        } catch(_) {}
    });
    log("libpairipcore.so nuked");
    Process.setExceptionHandler(function(ex) {
        if (ex.type === "access-violation" || ex.type === "illegal-instruction") {
            try { ex.context.rip = ex.context.rip.add(1); } catch(_) {}
            return true;
        }
        return false;
    });
})();

Java.perform(function() {
    log("启动 — 注入 plus-1-month-free-trial");

    try {
        Java.use("com.pairip.VMRunner").invoke.implementation = function() { return null; };
        Java.use("com.pairip.VMRunner$1").run.implementation = function() {};
    } catch(_) {}

    try {
        var TM = Java.use("com.android.org.conscrypt.TrustManagerImpl");
        TM.checkTrustedRecursive.overload(
            "[Ljava.security.cert.X509Certificate;", "java.net.Socket",
            "boolean", "boolean", "boolean",
            "java.util.Collection", "java.util.Collection"
        ).implementation = function() { return Java.use("java.util.ArrayList").$new(); };
    } catch(_) {}
    try {
        Java.use("android.security.net.config.NetworkSecurityTrustManager")
            .checkPins.implementation = function() {};
    } catch(_) {}
    try {
        Java.use("android.net.http.X509TrustManagerExtensions")
            .checkServerTrusted.overload(
                "[Ljava.security.cert.X509Certificate;",
                "java.lang.String", "java.lang.String"
            ).implementation = function() { return Java.use("java.util.ArrayList").$new(); };
    } catch(_) {}

    var JStr = Java.use("java.lang.String");
    try {
        var Bundle = Java.use("android.os.Bundle");
        Bundle.putStringArrayList
            .overload("java.lang.String", "java.util.ArrayList")
            .implementation = function(key, value) {
                if ((key === "SKU_OFFER_ID_TOKEN_LIST" ||
                     key === "OFFER_ID_TOKEN_LIST") && value) {
                    for (var i = 0; i < value.size(); i++)
                        value.set(i, JStr.$new(OFFER_TOKEN));
                    log("offerToken 已注入");
                }
                return this.putStringArrayList(key, value);
            };
    } catch(_) {}

    try {
        var JSONObj = Java.use("org.json.JSONObject");
        JSONObj.$init.overload("java.lang.String").implementation = function(s) {
            if (s && s.indexOf("oai.chatgpt.plus") !== -1 &&
                s.indexOf("offerToken") !== -1) {
                var patched = s.replace(
                    /"offerToken"\s*:\s*"[^"]+"/g,
                    '"offerToken":"' + OFFER_TOKEN + '"'
                );
                return this.$init(patched);
            }
            return this.$init(s);
        };
    } catch(_) {}

    log("就绪。请在 ChatGPT 中点击订阅按钮。");
});