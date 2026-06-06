// ==UserScript==
// @name         Miho-spot 评论增强
// @namespace    miho-spot
// @version      1.2
// @match        https://www.bilibili.com/video/*
// @grant        GM_xmlhttpRequest
// @grant        GM_setValue
// @grant        GM_getValue
// @grant        GM_setClipboard
// @grant        GM_notification
// @run-at       document-end
// ==/UserScript==

(function() {
"use strict";

// ── 动态配置（首次用初始值，后续从 GM 存储读取）──
var PRESETS = {
    style: GM_getValue("miho_style", "%%STYLE%%"),
    stance: GM_getValue("miho_stance", "%%STANCE%%"),
    诉求: GM_getValue("miho_su", "%%诉求%%"),
};

function savePresets() {
    GM_setValue("miho_style", PRESETS.style);
    GM_setValue("miho_stance", PRESETS.stance);
    GM_setValue("miho_su", PRESETS.诉求);
}

var API = "%%API_BASE%%";
var TAGGED_ATTR = "data-miho-tagged";

// ── Shadow DOM 穿透 ──
function deepQuery(el, selectors) {
    for (var i = 0; i < selectors.length; i++) {
        if (!el) return null;
        el = el.shadowRoot ? el.shadowRoot.querySelector(selectors[i]) : el.querySelector(selectors[i]);
    }
    return el;
}

// ── 注入标签 ──
function injectTag(commentBody, result) {
    var footer = commentBody.querySelector("#footer");
    if (!footer) return;
    var tagBar = document.createElement("div");
    tagBar.style.cssText = "display:flex;gap:6px;margin:6px 0;font-size:12px;align-items:center";
    tagBar.setAttribute(TAGGED_ATTR, "1");

    var colors = { pro: "#22c55e", anti: "#ef4444", neutral: "#f59e0b", rational: "#3b82f6", emotional: "#f97316" };
    var labels = { pro: "挺米", anti: "反米", neutral: "中性", rational: "理性", emotional: "感性" };

    var tags = [["stance", result.stance], ["emotion", result.emotion]];
    for (var t = 0; t < tags.length; t++) {
        var tag = tags[t][1];
        var span = document.createElement("span");
        span.textContent = labels[tag] || tag;
        span.style.cssText = "padding:1px 6px;border-radius:3px;color:#fff;font-weight:bold;background:" + (colors[tag] || "#666");
        tagBar.appendChild(span);
    }

    var btn = document.createElement("button");
    btn.textContent = "🤖 DeepSeek 话术";
    btn.style.cssText = "margin-left:auto;padding:3px 10px;border:1px solid #6366f1;border-radius:4px;background:linear-gradient(135deg,#1e1b4b,#312e81);color:#a5b4fc;cursor:pointer;font-size:11px;font-weight:bold";
    btn.onclick = function() { generateHuashu(commentBody); };
    tagBar.appendChild(btn);
    footer.parentNode.insertBefore(tagBar, footer.nextSibling);
}

// ── 生成话术 ──
async function generateHuashu(commentBody) {
    var richText = commentBody.querySelector("#content bili-rich-text");
    if (!richText || !richText.shadowRoot) return;
    var contents = richText.shadowRoot.querySelector("#contents");
    var text = contents ? contents.textContent.trim() : "";
    if (!text) return;

    var headerHTML = '<div style="display:flex;justify-content:flex-end;align-items:center;gap:6px;margin-bottom:4px"><span class="miho-regen-btn" style="cursor:pointer;color:#818cf8;font-size:11px;user-select:none" title="重新生成">🔄 重新生成</span><span class="miho-close-panel" style="cursor:pointer;color:#64748b;font-size:14px;user-select:none" title="关闭">&times;</span></div>';

    function bindPanelHeader() {
        panel.querySelector(".miho-close-panel").onclick = function() { panel.remove(); };
        var regen = panel.querySelector(".miho-regen-btn");
        if (regen) regen.onclick = function() { panel.remove(); generateHuashu(commentBody); };
    }

    var panel = document.createElement("div");
    panel.style.cssText = "position:relative;padding:8px 12px;margin:4px 0;background:#0f172a;border:1px solid #334155;border-radius:6px;font-size:12px;color:#94a3b8";
    panel.innerHTML = headerHTML + "<p>🤖 正在生成话术...</p>";
    bindPanelHeader();
    commentBody.querySelector("#main").appendChild(panel);

    try {
        var resp = await gmFetch("POST", "/comment/huashu", {
            comment_text: text, stance: PRESETS.stance, style: PRESETS.style, 诉求: PRESETS.诉求,
        });
        if (resp.ok && resp.huashus) {
            panel.innerHTML = headerHTML + resp.huashus.map(function(h) {
                return '<div style="margin-bottom:6px;border-left:3px solid #6366f1;padding-left:8px">' +
                    '<div style="color:#cbd5e1;margin-bottom:4px">' + h.text + '</div>' +
                    '<div style="display:flex;gap:8px;align-items:center">' +
                    '<span style="color:#64748b;font-size:10px">有效度:' + h.effectiveness + ' | ' + h.strategy + '</span>' +
                    '<button class="miho-copy-btn" data-text="' + h.text.replace(/"/g,"&quot;") + '" style="padding:1px 8px;background:#6366f1;color:#fff;border:none;border-radius:3px;cursor:pointer;font-size:11px">📋 复制</button>' +
                    '</div></div>';
            }).join("");
            bindPanelHeader();
            setTimeout(function() { bindCopyButtons(panel); }, 100);
        } else {
            panel.innerHTML = headerHTML + "<p style='color:#ef4444'>❌ 生成失败</p>";
            bindPanelHeader();
        }
    } catch(e) {
        panel.innerHTML = headerHTML + "<p style='color:#ef4444'>❌ 请求错误: " + e.message + "</p>";
        bindPanelHeader();
    }
}

function bindCopyButtons(panel) {
    var btns = (panel || document).querySelectorAll(".miho-copy-btn");
    console.log("[Miho-spot] bindCopyButtons: found " + btns.length + " copy buttons");
    if (!btns.length) {
        console.log("[Miho-spot] WARNING: no .miho-copy-btn elements found in scope");
        return;
    }
    btns.forEach(function(btn) {
        btn.onclick = function() {
            var text = this.getAttribute("data-text");
            console.log("[Miho-spot] copy clicked, text length=" + text.length);
            try {
                copyViaInject(text);
                console.log("[Miho-spot] copyViaInject executed OK");
                this.textContent = "✅ 已复制";
                this.style.background = "#22c55e";
                setTimeout(function() { btn.textContent = "📋 复制"; btn.style.background = "#6366f1"; }, 1500);
            } catch(e) {
                console.error("[Miho-spot] copy error:", e.message, e.stack);
                this.textContent = "❌ " + e.message;
                this.style.background = "#ef4444";
                setTimeout(function() { btn.textContent = "📋 复制"; btn.style.background = "#6366f1"; }, 3000);
            }
        };
    });
}

// 注入 script 到页面上下文执行复制，绕过油猴沙箱
function copyViaInject(text) {
    var s = document.createElement("script");
    // 将文本直接内联到 script 中，避免跨 window 引用丢失
    s.textContent = "(function(){var t=document.createElement('textarea');t.value=" + JSON.stringify(text) + ";t.style.cssText='position:fixed;top:-9999px';document.body.appendChild(t);t.select();var ok=document.execCommand('copy');document.body.removeChild(t);console.log('[Miho-page] copy result:',ok)})()";
    (document.head || document.documentElement).appendChild(s);
    s.remove();
}

function gmFetch(method, path, body) {
    return new Promise(function(resolve, reject) {
        GM_xmlhttpRequest({
            method: method, url: API + path,
            headers: { "Content-Type": "application/json" },
            data: JSON.stringify(body), timeout: 30000,
            onload: function(r) { try { resolve(JSON.parse(r.responseText)); } catch(e) { reject(e); } },
            onerror: function(e) { reject(e); },
            ontimeout: function() { reject(new Error("timeout")); },
        });
    });
}

async function analyzeBatch(comments) {
    var texts = comments.map(function(c) { return c.text; }).filter(function(t) { return t.length > 0; });
    if (!texts.length) return [];
    try {
        var body = { comments: texts.map(function(t) { return { text: t }; }) };
        var resp = await gmFetch("POST", "/comment/analyze", body);
        return resp.results || [];
    } catch(e) { return []; }
}

function findAllComments() {
    var results = [];
    var app = document.querySelector("#commentapp");
    if (!app) { return results; }
    var biliComments = app.querySelector("bili-comments");
    if (!biliComments || !biliComments.shadowRoot) { return results; }
    var feed = biliComments.shadowRoot.querySelector("#feed");
    if (!feed) { return results; }
    var threads = feed.querySelectorAll("bili-comment-thread-renderer");
    for (var i = 0; i < threads.length; i++) {
        var thread = threads[i];
        var renderer = thread.shadowRoot ? thread.shadowRoot.querySelector("bili-comment-renderer#comment") : null;
        if (!renderer || !renderer.shadowRoot) continue;
        var body = renderer.shadowRoot.querySelector("#body");
        if (!body || body.querySelector("[" + TAGGED_ATTR + "]")) continue;
        var richText = body.querySelector("#content bili-rich-text");
        if (!richText || !richText.shadowRoot) continue;
        var contents = richText.shadowRoot.querySelector("#contents");
        if (!contents) continue;
        var text = contents.textContent.trim();
        if (text.length < 5) continue;
        results.push({ body: body, text: text });
    }
    return results;
}

var isScanning = false;
async function scanAndTag() {
    if (isScanning) return;
    isScanning = true;
    try {
        var comments = findAllComments();
        if (!comments.length) { isScanning = false; return; }
        var results = await analyzeBatch(comments);
        results.forEach(function(r, i) {
            if (r && r.stance) injectTag(comments[i].body, r);
        });
    } finally {
        isScanning = false;
    }
}

// ── 浮动控制面板 ──
function buildControlPanel() {
    var container = document.createElement("div");
    container.id = "miho-ctl-panel";
    container.style.cssText = "position:fixed;top:120px;right:16px;z-index:99999;font-family:Arial,sans-serif";

    // 齿轮按钮
    var gear = document.createElement("div");
    gear.style.cssText = "width:36px;height:36px;background:linear-gradient(135deg,#6366f1,#8b5cf6);border-radius:50%;display:flex;align-items:center;justify-content:center;cursor:pointer;box-shadow:0 2px 8px rgba(99,102,241,0.4);font-size:16px;color:#fff";
    gear.textContent = "⚙";
    gear.title = "Miho-spot 评论增强设置";

    // 设置弹窗
    var popup = document.createElement("div");
    popup.style.cssText = "display:none;position:absolute;top:44px;right:0;width:260px;background:#0f172a;border:1px solid #334155;border-radius:8px;padding:14px;box-shadow:0 4px 20px rgba(0,0,0,0.5)";

    function buildPopupHTML() {
        var su = PRESETS.诉求.replace(/"/g,"&quot;");
        return '<div style="color:#e2e8f0;font-size:13px;font-weight:bold;margin-bottom:10px">⚙ 评论增强设置</div>' +
            '<div style="margin-bottom:8px"><div style="color:#94a3b8;font-size:11px;margin-bottom:3px">话术风格</div>' +
            '<select id="miho-cfg-style" style="width:100%;background:#1e293b;border:1px solid #334155;color:#e0e0e0;padding:4px 8px;border-radius:4px;font-size:12px">' +
            '<option value="理性"' + (PRESETS.style==="理性"?" selected":"") + '>理性分析</option>' +
            '<option value="感性"' + (PRESETS.style==="感性"?" selected":"") + '>情感共鸣</option>' +
            '<option value="幽默"' + (PRESETS.style==="幽默"?" selected":"") + '>幽默反击</option></select></div>' +
            '<div style="margin-bottom:8px"><div style="color:#94a3b8;font-size:11px;margin-bottom:3px">立场倾向</div>' +
            '<select id="miho-cfg-stance" style="width:100%;background:#1e293b;border:1px solid #334155;color:#e0e0e0;padding:4px 8px;border-radius:4px;font-size:12px">' +
            '<option value="挺米"' + (PRESETS.stance==="挺米"?" selected":"") + '>挺米</option>' +
            '<option value="反米"' + (PRESETS.stance==="反米"?" selected":"") + '>反米</option></select></div>' +
            '<div style="margin-bottom:10px"><div style="color:#94a3b8;font-size:11px;margin-bottom:3px">自定义诉求</div>' +
            '<input id="miho-cfg-su" value="' + su + '" placeholder="反驳关于XX的观点..." style="width:100%;box-sizing:border-box;background:#1e293b;border:1px solid #334155;color:#e0e0e0;padding:4px 8px;border-radius:4px;font-size:12px"></div>' +
            '<div style="display:flex;gap:6px">' +
            '<button id="miho-cfg-save" style="flex:1;padding:6px;background:#6366f1;color:#fff;border:none;border-radius:4px;cursor:pointer;font-size:12px;font-weight:bold">💾 保存并刷新</button>' +
            '<button id="miho-cfg-close" style="padding:6px 12px;background:#1e293b;color:#94a3b8;border:1px solid #334155;border-radius:4px;cursor:pointer;font-size:12px">✕</button></div>';
    }

    popup.innerHTML = buildPopupHTML();
    gear.onclick = function() { popup.style.display = popup.style.display === "none" ? "block" : "none"; };

    container.appendChild(gear);
    container.appendChild(popup);
    document.body.appendChild(container);

    // 事件绑定
    document.getElementById("miho-cfg-save").onclick = function() {
        PRESETS.style = document.getElementById("miho-cfg-style").value;
        PRESETS.stance = document.getElementById("miho-cfg-stance").value;
        PRESETS.诉求 = document.getElementById("miho-cfg-su").value;
        savePresets();
        popup.style.display = "none";
        console.log("[Miho-spot] 设置已更新:", PRESETS.style, PRESETS.stance);
        // 清除已有标签，重新分析
        document.querySelectorAll("[" + TAGGED_ATTR + "]").forEach(function(el) { el.remove(); });
        scanAndTag();
    };
    document.getElementById("miho-cfg-close").onclick = function() { popup.style.display = "none"; };
}

// ── 初始化 ──
var scanTimer = null;
buildControlPanel();
setTimeout(function() {
    scanAndTag();
    scanTimer = setInterval(scanAndTag, 3000);
}, 2000);

var lastUrl = location.href;
new MutationObserver(function() {
    if (location.href !== lastUrl) {
        lastUrl = location.href;
        clearInterval(scanTimer);
        setTimeout(function() { scanAndTag(); scanTimer = setInterval(scanAndTag, 3000); }, 2000);
    }
}).observe(document, { subtree: true, childList: true });

console.log("[Miho-spot] 评论增强脚本已就绪 | 风格:" + PRESETS.style + " 立场:" + PRESETS.stance);
})();
