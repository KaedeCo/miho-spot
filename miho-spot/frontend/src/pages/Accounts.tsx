import { useEffect, useState } from "react";
import { Button, Input, Dialog, MessagePlugin, Space } from "tdesign-react";
import { CheckCircleIcon, CloseCircleIcon, RefreshIcon } from "tdesign-icons-react";
import { verifyAccount, saveAccount, verifyDeepSeek, getDeepSeekStatus } from "../services/api";

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

  useEffect(() => { loadDsStatus(); }, []);

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
    </div>
  );
}
