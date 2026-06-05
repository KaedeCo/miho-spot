import { useEffect, useState } from "react";
import { Button, Input, Dialog, MessagePlugin, Space, Textarea } from "tdesign-react";
import { CheckCircleIcon, CloseCircleIcon, RefreshIcon } from "tdesign-icons-react";
import { verifyAccount, saveAccount, verifyDeepSeek, getDeepSeekStatus, getAccounts, verifyVolcano, verifyTavily, getSearchStatus, testVolcanoSearch, testTavilySearch } from "../services/api";

const API_KEY_DEFAULT = "";
const STORAGE_KEY = "miho_accounts_v3";

interface AccountState {
  apiKey: string;
  isValid: boolean;
  lastVerified: string;
}

function load(): AccountState {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    if (raw) return JSON.parse(raw);
  } catch {}
  return { apiKey: API_KEY_DEFAULT, isValid: false, lastVerified: "" };
}

function persist(s: AccountState) {
  localStorage.setItem(STORAGE_KEY, JSON.stringify(s));
}

export default function Accounts() {
  const [state, setState] = useState<AccountState>(() => load());
  const [dialogVisible, setDialogVisible] = useState(false);
  const [editKey, setEditKey] = useState("");
  const [verifying, setVerifying] = useState(false);

  // DeepSeek states
  const [dsConfigured, setDsConfigured] = useState(false);
  const [dsValid, setDsValid] = useState(false);
  const [dsDlgVisible, setDsDlgVisible] = useState(false);
  const [dsKey, setDsKey] = useState("");
  const [dsVerifying, setDsVerifying] = useState(false);

  // Volcano states
  const [vaConfigured, setVaConfigured] = useState(false);
  const [vaDlgVisible, setVaDlgVisible] = useState(false);
  const [vaKey, setVaKey] = useState("");
  const [vaBotId, setVaBotId] = useState("");
  const [vaVerifying, setVaVerifying] = useState(false);

  // Tavily states
  const [tvConfigured, setTvConfigured] = useState(false);
  const [tvDlgVisible, setTvDlgVisible] = useState(false);
  const [tvKey, setTvKey] = useState("");
  const [tvVerifying, setTvVerifying] = useState(false);

  // Test search result states
  const [testResult, setTestResult] = useState<{ title: string; content: string } | null>(null);
  const [testDlgVisible, setTestDlgVisible] = useState(false);
  const [testing, setTesting] = useState(false);

  // Bilibili cookie states - multi-field
  interface BiliCookieFields {
    SESSDATA: string;
    bili_jct: string;
    buvid3: string;
    DedeUserID: string;
    DedeUserID__ckMd5: string;
  }
  const [biliCookie, setBiliCookie] = useState("");
  const [biliValid, setBiliValid] = useState(false);
  const [biliDlgVisible, setBiliDlgVisible] = useState(false);
  const [biliFields, setBiliFields] = useState<BiliCookieFields>({
    SESSDATA: "",
    bili_jct: "",
    buvid3: "",
    DedeUserID: "",
    DedeUserID__ckMd5: "",
  });
  const [biliSaving, setBiliSaving] = useState(false);
  const [biliVerifying, setBiliVerifying] = useState(false);

  useEffect(() => { loadDsStatus(); loadBiliStatus(); loadSearchStatus(); }, []);

  const loadSearchStatus = async () => {
    try {
      const r = await getSearchStatus();
      setVaConfigured(r.volcano?.isValid || false);
      setTvConfigured(r.tavily?.isValid || false);
    } catch {}
  };

  const loadDsStatus = async () => {
    try {
      const r = await getDeepSeekStatus();
      setDsConfigured(r.configured);
      setDsValid(r.isValid);
    } catch { setDsConfigured(false); setDsValid(false); }
  };

  const doVerify = async () => {
    setVerifying(true);
    try {
      const r = await verifyAccount("tophub", state.apiKey);
      const updated = { ...state, isValid: r.isValid, lastVerified: new Date().toISOString() };
      setState(updated); persist(updated);
      MessagePlugin[r.isValid ? "success" : "warning"](r.isValid ? `已连接 (${r.message || ""})` : (r.message || "验证失败"));
    } catch { MessagePlugin.error("后端未连接"); }
    finally { setVerifying(false); }
  };

  const openChangeDialog = () => {
    setEditKey(state.apiKey);
    setDialogVisible(true);
  };

  const doSave = () => {
    if (!editKey.trim()) { MessagePlugin.warning("请输入API Key"); return; }
    const updated = { ...state, apiKey: editKey.trim(), isValid: false, lastVerified: "" };
    setState(updated); persist(updated);
    saveAccount({ platform: "tophub", username: editKey.trim(), cookie: "", isValid: false, lastVerified: "" }).catch(() => {});
    setDialogVisible(false);
    MessagePlugin.success("已保存，请重新验证");
  };

  // --- DeepSeek handlers ---
  const handleDsVerify = async () => {
    if (!dsKey.trim()) { MessagePlugin.warning("请输入DeepSeek API Key"); return; }
    setDsVerifying(true);
    try {
      const r = await verifyDeepSeek(dsKey.trim());
      MessagePlugin[r.isValid ? "success" : "warning"](r.message);
      if (r.isValid) { setDsConfigured(true); setDsValid(true); setDsDlgVisible(false); setDsKey(""); }
    } catch { MessagePlugin.error("后端未连接"); }
    finally { setDsVerifying(false); }
  };

  // --- Volcano handlers ---
  const handleVaVerify = async () => {
    if (!vaKey.trim()) { MessagePlugin.warning("请输入火山方舟 API Key"); return; }
    if (!vaBotId.trim()) { MessagePlugin.warning("请输入端点 ID"); return; }
    setVaVerifying(true);
    try {
      const r = await verifyVolcano(vaKey.trim(), vaBotId.trim());
      MessagePlugin[r.isValid ? "success" : "warning"](r.message);
      if (r.isValid) { setVaConfigured(true); setVaDlgVisible(false); setVaKey(""); setVaBotId(""); }
    } catch { MessagePlugin.error("后端未连接"); }
    finally { setVaVerifying(false); }
  };

  // --- Tavily handlers ---
  const handleTvVerify = async () => {
    if (!tvKey.trim()) { MessagePlugin.warning("请输入 Tavily API Key"); return; }
    setTvVerifying(true);
    try {
      const r = await verifyTavily(tvKey.trim());
      MessagePlugin[r.isValid ? "success" : "warning"](r.message);
      if (r.isValid) { setTvConfigured(true); setTvDlgVisible(false); setTvKey(""); }
    } catch { MessagePlugin.error("后端未连接"); }
    finally { setTvVerifying(false); }
  };

  // --- Test search handlers ---
  const handleTestVolcano = async () => {
    setTesting(true);
    try {
      const r = await testVolcanoSearch();
      if (r.ok && r.results?.length) {
        setTestResult({ title: '火山方舟搜索测试结果', content: r.results[0]?.substring?.(0, 1000) || String(r.results[0]) });
      } else {
        setTestResult({ title: '测试失败', content: r.error || '未知错误' });
      }
      setTestDlgVisible(true);
    } catch { MessagePlugin.error("测试请求失败"); }
    finally { setTesting(false); }
  };

  const handleTestTavily = async () => {
    setTesting(true);
    try {
      const r = await testTavilySearch();
      if (r.ok && r.results?.length) {
        const items = r.results.map((it: any) => `[${it.title}](${it.url})\n${it.content}`).join('\n\n');
        setTestResult({ title: 'Tavily 搜索测试结果', content: items.substring(0, 1500) });
      } else {
        setTestResult({ title: '测试失败', content: r.error || '未知错误' });
      }
      setTestDlgVisible(true);
    } catch { MessagePlugin.error("测试请求失败"); }
    finally { setTesting(false); }
  };

  // --- Bilibili handlers ---
  const loadBiliStatus = async () => {
    try {
      const accounts = await getAccounts();
      const bili = Array.isArray(accounts) ? accounts.find((a: any) => a.platform === "bilibili") : null;
      if (bili && bili.cookie) {
        setBiliCookie(bili.cookie);
        setBiliValid(bili.isValid || false);
        // Parse existing cookie string into fields
        const fields: BiliCookieFields = { SESSDATA: "", bili_jct: "", buvid3: "", DedeUserID: "", DedeUserID__ckMd5: "" };
        bili.cookie.split(";").forEach((part: string) => {
          const [key, ...valParts] = part.trim().split("=");
          if (key && valParts.length) {
            const v = valParts.join("=");
            if (key in fields) (fields as any)[key] = v;
          }
        });
        setBiliFields(fields);
      }
    } catch {}
  };

  /** Build cookie string from individual fields */
  const buildCookieString = (f: BiliCookieFields): string => {
    return Object.entries(f)
      .filter(([, v]) => v.trim())
      .map(([k, v]) => `${k}=${v.trim()}`)
      .join("; ");
  };

  const handleBiliVerify = async () => {
    if (!biliFields.SESSDATA.trim()) { MessagePlugin.warning("至少需要填写 SESSDATA 字段才能验证"); return; }
    setBiliVerifying(true);
    try {
      const cookieStr = buildCookieString(biliFields);
      const r = await verifyAccount("bilibili", cookieStr);
      if (r.isValid) {
        MessagePlugin.success(r.message || "Cookie验证通过");
      } else {
        MessagePlugin.warning(r.message || "Cookie无效");
      }
    } catch { MessagePlugin.error("后端未连接"); }
    finally { setBiliVerifying(false); }
  };

  const handleBiliSave = async () => {
    if (!biliFields.SESSDATA.trim()) { MessagePlugin.warning("至少需要填写 SESSDATA 字段"); return; }
    setBiliSaving(true);
    try {
      const cookieStr = buildCookieString(biliFields);
      await saveAccount({ platform: "bilibili", username: biliFields.DedeUserID || "", cookie: cookieStr, isValid: true, lastVerified: new Date().toISOString() });
      setBiliCookie(cookieStr);
      setBiliValid(true);
      setBiliDlgVisible(false);
      MessagePlugin.success("B站Cookie已保存");
    } catch { MessagePlugin.error("后端未连接，请检查后端是否启动"); }
    finally { setBiliSaving(false); }
  };

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div>
        <h1 className="text-2xl font-bold text-white">账号管理</h1>
        <p className="text-sm text-[#94a3b8] mt-1">Tophub API 密钥和 DeepSeek AI 情感分析配置</p>
      </div>

      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Tophub Card */}
        <div className="glass-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-lg flex items-center justify-center text-white font-bold text-lg" style={{ backgroundColor: "#f59e0b" }}>H</div>
            <div>
              <h3 className="font-semibold text-white">Tophub API</h3>
              <div className="flex items-center gap-1 mt-0.5">
                {state.isValid ? (
                  <><CheckCircleIcon style={{ fontSize: 14, color: "#22c55e" }} /><span className="text-xs text-green-500">已连接</span></>
                ) : (
                  <><CloseCircleIcon style={{ fontSize: 14, color: "#64748b" }} /><span className="text-xs text-[#64748b]">未验证</span></>
                )}
              </div>
            </div>
          </div>

          <p className="text-sm text-[#94a3b8] mb-2">API Key: ******{state.apiKey.slice(-4)}</p>
          {state.lastVerified && <p className="text-xs text-[#555] mb-4">最后验证: {new Date(state.lastVerified).toLocaleString("zh-CN")}</p>}

          <Space>
            <Button theme="primary" icon={<RefreshIcon />} loading={verifying} onClick={doVerify}>验证连接</Button>
            <Button variant="outline" icon={<RefreshIcon />} onClick={openChangeDialog}>更改密钥</Button>
          </Space>
        </div>

        {/* Bilibili Cookie Card */}
        <div className="glass-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-lg flex items-center justify-center text-white font-bold text-lg" style={{ backgroundColor: "#fb7299" }}>B</div>
            <div>
              <h3 className="font-semibold text-white">B站 Cookie</h3>
              <div className="flex items-center gap-1 mt-0.5">
                {biliValid ? (
                  <><CheckCircleIcon style={{ fontSize: 14, color: "#22c55e" }} /><span className="text-xs text-green-500">已配置</span></>
                ) : (
                  <><CloseCircleIcon style={{ fontSize: 14, color: "#64748b" }} /><span className="text-xs text-[#64748b]">未配置</span></>
                )}
              </div>
            </div>
          </div>

          <p className="text-sm text-[#94a3b8] mb-1">
            {biliValid
              ? "B站 Cookie 已配置，评论拉取将使用已登录身份，绕过反爬限制"
              : "配置后可使用已登录身份拉取 B站评论数据，大幅提升稳定性（未配置时使用免费代理API）"}
          </p>
          <p className="text-xs text-[#555] mb-4">
            获取方法: 登录B站后，按F12 → Application → Cookies → 复制 SESSDATA 等字段
          </p>

          <Space>
            <Button theme="primary" icon={<RefreshIcon />} onClick={() => { loadBiliStatus(); setBiliDlgVisible(true); }}>
              {biliValid ? "更换Cookie" : "配置Cookie"}
            </Button>
            {biliValid && <Button variant="outline" onClick={loadBiliStatus}>刷新状态</Button>}
          </Space>
        </div>

        {/* DeepSeek Card */}
        <div className="glass-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-lg flex items-center justify-center text-white font-bold text-lg" style={{ backgroundColor: "#6366f1" }}>D</div>
            <div>
              <h3 className="font-semibold text-white">DeepSeek AI</h3>
              <p className="text-xs text-[#94a3b8] mt-0.5">精准情感分析引擎</p>
              <div className="flex items-center gap-1 mt-1">
                {dsValid ? (
                  <><CheckCircleIcon style={{ fontSize: 14, color: "#22c55e" }} /><span className="text-xs text-green-500">已激活</span></>
                ) : dsConfigured ? (
                  <><CloseCircleIcon style={{ fontSize: 14, color: "#f59e0b" }} /><span className="text-xs text-yellow-500">密钥失效</span></>
                ) : (
                  <><CloseCircleIcon style={{ fontSize: 14, color: "#64748b" }} /><span className="text-xs text-[#64748b]">未配置</span></>
                )}
              </div>
            </div>
          </div>

          <p className="text-sm text-[#94a3b8] mb-1">
            {dsConfigured ? "DeepSeek API 已配置，热搜标题将使用AI精准分析情感倾向" : "配置后可使用 DeepSeek AI 替代本地分析，大幅提升情感判断准确率"}
          </p>
          <p className="text-xs text-[#555] mb-4">
            获取API Key: <a href="https://platform.deepseek.com/api_keys" target="_blank" rel="noopener noreferrer" className="text-indigo-400 hover:text-indigo-300">platform.deepseek.com</a>
          </p>

          <Space>
            <Button theme="primary" icon={<RefreshIcon />} loading={dsVerifying} onClick={() => { setDsKey(""); setDsDlgVisible(true); }}>
              {dsConfigured ? "更换密钥" : "配置 DeepSeek"}
            </Button>
            {dsConfigured && <Button variant="outline" onClick={loadDsStatus}>刷新状态</Button>}
          </Space>
        </div>

        {/* Volcano Ark Card */}
        <div className="glass-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-lg flex items-center justify-center text-white font-bold text-lg" style={{ backgroundColor: "#f97316" }}>V</div>
            <div>
              <h3 className="font-semibold text-white">火山方舟</h3>
              <p className="text-xs text-[#94a3b8] mt-0.5">智能体联网搜索（主轨）</p>
              <div className="flex items-center gap-1 mt-1">
                {vaConfigured ? (
                  <><CheckCircleIcon style={{ fontSize: 14, color: "#22c55e" }} /><span className="text-xs text-green-500">已激活</span></>
                ) : (
                  <><CloseCircleIcon style={{ fontSize: 14, color: "#94a3b8" }} /><span className="text-xs text-[#94a3b8]">未配置</span></>
                )}
              </div>
            </div>
          </div>

          <p className="text-sm text-[#94a3b8] mb-1">
            {vaConfigured ? "火山方舟 Bot 已配置，辩论 Agent 将通过联网插件进行搜索（月免2万次）" : "配置后 Agent 辩论将通过火山方舟 Bot 进行联网搜索，每月免费2万次"}
          </p>
          <p className="text-xs text-[#555] mb-4">
            获取: <a href="https://console.volcengine.com/ark" target="_blank" rel="noopener noreferrer" className="text-orange-400 hover:text-orange-300">console.volcengine.com</a> → 在线推理 → 创建接入点(DeepSeek-V3.2) → 复制端点ID
          </p>

          <Space>
            <Button theme="primary" icon={<RefreshIcon />} loading={vaVerifying} onClick={() => { setVaKey(""); setVaBotId(""); setVaDlgVisible(true); }}>
              {vaConfigured ? "更换配置" : "配置火山方舟"}
            </Button>
            {vaConfigured && <Button variant="outline" onClick={loadSearchStatus}>刷新状态</Button>}
            {vaConfigured && <Button variant="outline" loading={testing} onClick={handleTestVolcano}>🧪 测试搜索</Button>}
          </Space>
        </div>

        {/* Tavily Card */}
        <div className="glass-card p-6">
          <div className="flex items-center gap-3 mb-4">
            <div className="w-12 h-12 rounded-lg flex items-center justify-center text-white font-bold text-lg" style={{ backgroundColor: "#3b82f6" }}>T</div>
            <div>
              <h3 className="font-semibold text-white">Tavily Search</h3>
              <p className="text-xs text-[#94a3b8] mt-0.5">AI 搜索引擎（备轨）</p>
              <div className="flex items-center gap-1 mt-1">
                {tvConfigured ? (
                  <><CheckCircleIcon style={{ fontSize: 14, color: "#22c55e" }} /><span className="text-xs text-green-500">已激活</span></>
                ) : (
                  <><CloseCircleIcon style={{ fontSize: 14, color: "#94a3b8" }} /><span className="text-xs text-[#94a3b8]">未配置</span></>
                )}
              </div>
            </div>
          </div>

          <p className="text-sm text-[#94a3b8] mb-1">
            {tvConfigured ? "Tavily 已配置，火山方舟配额耗尽时将自动切换到此备轨" : "配置后作为备轨——火山方舟月免用完后自动切换，每月免费1000次"}
          </p>
          <p className="text-xs text-[#555] mb-4">
            获取API Key: <a href="https://tavily.com" target="_blank" rel="noopener noreferrer" className="text-blue-400 hover:text-blue-300">tavily.com</a>
          </p>

          <Space>
            <Button theme="primary" icon={<RefreshIcon />} loading={tvVerifying} onClick={() => { setTvKey(""); setTvDlgVisible(true); }}>
              {tvConfigured ? "更换密钥" : "配置 Tavily"}
            </Button>
            {tvConfigured && <Button variant="outline" onClick={loadSearchStatus}>刷新状态</Button>}
            {tvConfigured && <Button variant="outline" loading={testing} onClick={handleTestTavily}>🧪 测试搜索</Button>}
          </Space>
        </div>
      </div>

      {/* Change API Key Dialog */}
      <Dialog header="更改 Tophub API Key" visible={dialogVisible} onClose={() => setDialogVisible(false)} onConfirm={doSave} confirmBtn="保存" cancelBtn="取消" destroyOnClose width={500}>
        <div className="space-y-4 py-2">
          <p className="text-xs text-[#64748b]">输入新的 Tophub API Key，保存后需重新验证</p>
          <Input value={editKey} onChange={v => setEditKey(v as string)} placeholder="输入新的 API Key" />
        </div>
      </Dialog>

      {/* DeepSeek API Key Dialog */}
      <Dialog header="配置 DeepSeek API Key" visible={dsDlgVisible} onClose={() => setDsDlgVisible(false)} onConfirm={handleDsVerify} confirmBtn="验证并保存" cancelBtn="取消" destroyOnClose width={500}>
        <div className="space-y-4 py-2">
          <p className="text-xs text-[#64748b]">输入你的 DeepSeek API Key（sk-开头）。<br/>获取地址: platform.deepseek.com/api_keys</p>
          <Input value={dsKey} onChange={v => setDsKey(v as string)} placeholder="sk-xxxxxxxxxxxxxxxx" />
        </div>
      </Dialog>

      {/* Volcano Ark Dialog */}
      <Dialog header="配置火山方舟" visible={vaDlgVisible} onClose={() => setVaDlgVisible(false)} onConfirm={handleVaVerify} confirmBtn="验证并保存" cancelBtn="取消" destroyOnClose width={500}>
        <div className="space-y-4 py-2">
          <p className="text-xs text-[#64748b]">
            配置火山方舟模型接入点以启用联网搜索。<br/>
            1. 在 <a href="https://console.volcengine.com/ark" target="_blank" className="text-orange-400">火山方舟控制台</a> 创建 API Key<br/>
            2. 在线推理 → 创建接入点 → 选择 DeepSeek-V3.2<br/>
            3. 复制端点 ID（ep-xxx）和 API Key 填入下方
          </p>
          <div>
            <label className="text-xs text-[#94a3b8] block mb-1">API Key</label>
            <Input value={vaKey} onChange={v => setVaKey(v as string)} placeholder="火山方舟 API Key..." />
          </div>
          <div>
            <label className="text-xs text-[#94a3b8] block mb-1">端点 ID</label>
            <Input value={vaBotId} onChange={v => setVaBotId(v as string)} placeholder="ep-20260605220808-nt2nk" />
          </div>
        </div>
      </Dialog>

      {/* Tavily Dialog */}
      <Dialog header="配置 Tavily Search API" visible={tvDlgVisible} onClose={() => setTvDlgVisible(false)} onConfirm={handleTvVerify} confirmBtn="验证并保存" cancelBtn="取消" destroyOnClose width={500}>
        <div className="space-y-4 py-2">
          <p className="text-xs text-[#64748b]">
            配置 Tavily 作为备轨搜索引擎。<br/>
            获取 API Key: <a href="https://tavily.com" target="_blank" className="text-blue-400">tavily.com</a>（免费层每月 1000 次）
          </p>
          <Input value={tvKey} onChange={v => setTvKey(v as string)} placeholder="tvly-xxxxxxxxxxxxxxxx" />
        </div>
      </Dialog>

      {/* Test Search Result Dialog */}
      <Dialog header={testResult?.title || '测试结果'} visible={testDlgVisible} onClose={() => setTestDlgVisible(false)} cancelBtn={null} confirmBtn="关闭" onConfirm={() => setTestDlgVisible(false)} destroyOnClose width={700}>
        <div className="py-2 max-h-[60vh] overflow-y-auto">
          <pre className="text-xs text-[#94a3b8] bg-[#0a0a0f] p-4 rounded-lg whitespace-pre-wrap break-words leading-relaxed font-mono">
            {testResult?.content || '无结果'}
          </pre>
        </div>
      </Dialog>

      {/* Bilibili Cookie Dialog - Multi-field */}
      <Dialog
        header={
          <div className="flex items-center justify-between w-full pr-4">
            <span>配置 B站 Cookie</span>
            <Button
              size="small"
              variant="outline"
              theme="primary"
              loading={biliVerifying}
              onClick={(e) => { e.stopPropagation(); handleBiliVerify(); }}
            >
              验证 Cookie
            </Button>
          </div>
        }
        visible={biliDlgVisible}
        onClose={() => setBiliDlgVisible(false)}
        onConfirm={handleBiliSave}
        confirmBtn={{ content: "保存", loading: biliSaving }}
        cancelBtn="取消"
        destroyOnClose
        width={680}
        showOverlay
        closeOnOverlayClick
      >
        <div className="space-y-4 py-2">
          {/* Step-by-step guide */}
          <div className="bg-[#1e293b] rounded-lg p-3 border border-[#334155]">
            <p className="text-xs font-semibold text-white mb-2">📋 获取步骤：</p>
            <ol className="text-xs text-[#94a3b8] space-y-1 pl-4 list-decimal">
              <li>打开浏览器，访问 <span className="text-pink-400">bilibili.com</span> 并确保已登录</li>
              <li>按 <kbd className="px-1.5 py-0.5 bg-[#0f172a] rounded text-indigo-300 text-[10px]">F12</kbd> 打开开发者工具</li>
              <li>点击顶部 <span className="text-yellow-400">Application</span>（应用程序）标签</li>
              <li>左侧找到 <span className="text-green-400">Cookies → https://www.bilibili.com</span></li>
              <li>在右侧表格中找到下方列出的字段，复制对应的 <span className="text-indigo-400">Value</span> 值粘贴到输入框</li>
            </ol>
          </div>

          {/* Field definitions table */}
          <div className="text-xs space-y-1.5">
            <div className="flex items-center gap-2 font-semibold text-white mb-1">
              <span>字段说明</span>
              <span className="text-[10px] px-1.5 py-0.5 bg-red-500/20 text-red-400 rounded">必填</span>
              <span className="text-[10px] px-1.5 py-0.5 bg-yellow-500/20 text-yellow-400 rounded">推荐</span>
              <span className="text-[10px] px-1.5 py-0.5 bg-slate-500/20 text-slate-400 rounded">可选</span>
            </div>

            {/* SESSDATA */}
            <div className="grid grid-cols-[140px_1fr_auto] gap-2 items-center bg-[#1e293b]/50 rounded p-2">
              <div className="flex items-center gap-1.5">
                <code className="text-indigo-300 font-mono text-[11px]">SESSDATA</code>
                <span className="text-[9px] px-1 bg-red-500/20 text-red-400 rounded shrink-0">必填</span>
              </div>
              <Input
                value={biliFields.SESSDATA}
                onChange={(v) => setBiliFields({ ...biliFields, SESSDATA: v as string })}
                placeholder="粘贴 SESSDATA 的 Value 值..."
                size="small"
              />
              <span className="text-[10px] text-[#555] w-20 text-right">登录凭证</span>
            </div>

            {/* bili_jct */}
            <div className="grid grid-cols-[140px_1fr_auto] gap-2 items-center bg-[#1e293b]/50 rounded p-2">
              <div className="flex items-center gap-1.5">
                <code className="text-indigo-300 font-mono text-[11px]">bili_jct</code>
                <span className="text-[9px] px-1 bg-yellow-500/20 text-yellow-400 rounded shrink-0">推荐</span>
              </div>
              <Input
                value={biliFields.bili_jct}
                onChange={(v) => setBiliFields({ ...biliFields, bili_jct: v as string })}
                placeholder="粘贴 bili_jct 的 Value 值（可选）..."
                size="small"
              />
              <span className="text-[10px] text-[#555] w-20 text-right">CSRF令牌</span>
            </div>

            {/* buvid3 */}
            <div className="grid grid-cols-[140px_1fr_auto] gap-2 items-center bg-[#1e293b]/50 rounded p-2">
              <div className="flex items-center gap-1.5">
                <code className="text-indigo-300 font-mono text-[11px]">buvid3</code>
                <span className="text-[9px] px-1 bg-yellow-500/20 text-yellow-400 rounded shrink-0">推荐</span>
              </div>
              <Input
                value={biliFields.buvid3}
                onChange={(v) => setBiliFields({ ...biliFields, buvid3: v as string })}
                placeholder="粘贴 buvid3 的 Value 值（可选）..."
                size="small"
              />
              <span className="text-[10px] text-[#555] w-20 text-right">设备指纹</span>
            </div>

            {/* DedeUserID */}
            <div className="grid grid-cols-[140px_1fr_auto] gap-2 items-center bg-[#1e293b]/30 rounded p-2">
              <div className="flex items-center gap-1.5">
                <code className="text-indigo-300 font-mono text-[11px]">DedeUserID</code>
                <span className="text-[9px] px-1 bg-slate-500/20 text-slate-400 rounded shrink-0">可选</span>
              </div>
              <Input
                value={biliFields.DedeUserID}
                onChange={(v) => setBiliFields({ ...biliFields, DedeUserID: v as string })}
                placeholder="用户数字ID（可选）..."
                size="small"
              />
              <span className="text-[10px] text-[#555] w-20 text-right">用户ID</span>
            </div>

            {/* DedeUserID__ckMd5 */}
            <div className="grid grid-cols-[140px_1fr_auto] gap-2 items-center bg-[#1e293b]/30 rounded p-2">
              <div className="flex items-center gap-1.5">
                <code className="text-indigo-300 font-mono text-[11px] leading-tight">DedeUserID__ckMd5</code>
                <span className="text-[9px] px-1 bg-slate-500/20 text-slate-400 rounded shrink-0">可选</span>
              </div>
              <Input
                value={biliFields.DedeUserID__ckMd5}
                onChange={(v) => setBiliFields({ ...biliFields, DedeUserID__ckMd5: v as string })}
                placeholder="用户ID校验值（可选）..."
                size="small"
              />
              <span className="text-[10px] text-[#555] w-20 text-right">ID校验</span>
            </div>
          </div>

          {/* Quick reference summary */}
          <div className="border-t border-[#334155] pt-3 mt-2">
            <p className="text-[11px] text-[#64748b]">
              <span className="font-semibold text-white">最低配置：</span>仅需填写 <code className="text-red-400">SESSDATA</code> 即可拉取评论数据
            </p>
            <p className="text-[11px] text-[#64748b] mt-1">
              <span className="font-semibold text-white">完整配置：</span>建议填写前3个字段（SESSDATA + bili_jct + buvid3）以获得最佳稳定性
            </p>
            <p className="text-[10px] text-[#475569] mt-1.5">
              💡 Cookie 有效期通常为数月，失效后需重新获取。SESSDATA 是最核心的登录凭证。
            </p>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
