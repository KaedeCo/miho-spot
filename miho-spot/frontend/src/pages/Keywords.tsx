import { useEffect, useState } from "react";
import { Button, Input, Select, Table, Tag, Dialog, MessagePlugin, Popconfirm } from "tdesign-react";
import { AddIcon, DeleteIcon, SearchIcon, EditIcon, FolderAddIcon, DownloadIcon, UploadIcon, RefreshIcon } from "tdesign-icons-react";
import { useRef } from "react";
import type { KeywordEntry, CategoryEntry } from "../types";
import { KEYWORD_CATEGORIES } from "../types";
import { getKeywords, addKeyword, updateKeyword, deleteKeyword, getCategories, addCategory, updateCategory, deleteCategory, exportKeywords, importKeywords, resetKeywords } from "../services/api";

export default function Keywords() {
  const [keywords, setKeywords] = useState<KeywordEntry[]>([]);
  const [categories, setCategories] = useState<CategoryEntry | null>(null);
  const [loading, setLoading] = useState(true);
  const [searchText, setSearchText] = useState("");
  const [filterCategory, setFilterCategory] = useState<string>("all");
  const fileInputRef = useRef<HTMLInputElement>(null);

  // Add dialog
  const [addDlg, setAddDlg] = useState(false);
  const [newKw, setNewKw] = useState("");
  const [newCat, setNewCat] = useState<string>("general");

  // Edit dialog
  const [editDlg, setEditDlg] = useState(false);
  const [editId, setEditId] = useState("");
  const [editKw, setEditKw] = useState("");
  const [editCat, setEditCat] = useState("");

  // Category management dialog
  const [catDlg, setCatDlg] = useState(false);
  const [catEditKey, setCatEditKey] = useState("");
  const [catEditName, setCatEditName] = useState("");
  const [catAddKey, setCatAddKey] = useState("");
  const [catAddName, setCatAddName] = useState("");

  useEffect(() => { loadAll(); }, []);

  const loadAll = async () => {
    setLoading(true);
    try {
      const [kw, cat] = await Promise.all([getKeywords(), getCategories()]);
      setKeywords(kw || []);
      setCategories(cat || null);
    } catch {
      setKeywords([]);
      setCategories(null);
    }
    finally { setLoading(false); }
  };

  const catMap: Record<string, string> = {};
  const catEntries = categories?.categories || KEYWORD_CATEGORIES as any;
  const catList = Object.entries(catEntries).map(([k, v]) => ({ key: k, name: typeof v === "string" ? v : (v as any).name }));
  if (catList.length === 0) {
    catList.push(...Object.entries(KEYWORD_CATEGORIES).map(([k, v]) => ({ key: k, name: v })));
  }
  for (const c of catList) catMap[c.key] = c.name;

  const filtered = keywords.filter(kw => {
    const m = !searchText || kw.keyword.includes(searchText);
    const c = filterCategory === "all" || kw.category === filterCategory;
    return m && c;
  });

  const categoryOptions = [{ label: "全部", value: "all" }, ...catList.map(c => ({ label: c.name, value: c.key }))];
  const catEditOptions = catList.map(c => ({ label: c.name, value: c.key }));

  const catColors: Record<string, string> = { mihoyo_game: "#6366f1", mihoyo_character: "#a78bfa", mihoyo_cv: "#f59e0b", competitor: "#ef4444", general: "#6b7280" };
  const getCatColor = (key: string) => catColors[key] || "#8b5cf6";

  // --- Keyword handlers ---
  const handleAdd = async () => {
    if (!newKw.trim()) { MessagePlugin.warning("请输入关键词"); return; }
    try {
      await addKeyword({ keyword: newKw.trim(), category: newCat, addedBy: "user" } as any);
      setAddDlg(false); setNewKw(""); setNewCat("general");
      loadAll(); MessagePlugin.success("已添加");
    } catch { MessagePlugin.error("添加失败"); }
  };

  const openEdit = (row: KeywordEntry) => {
    setEditId(row.id);
    setEditKw(row.keyword);
    setEditCat(row.category);
    setEditDlg(true);
  };

  const handleEdit = async () => {
    if (!editKw.trim()) { MessagePlugin.warning("关键词不能为空"); return; }
    try {
      await updateKeyword(editId, { keyword: editKw.trim(), category: editCat });
      setEditDlg(false);
      loadAll();
      MessagePlugin.success("已更新");
    } catch { MessagePlugin.error("更新失败"); }
  };

  const handleDelete = async (id: string) => {
    try { await deleteKeyword(id); loadAll(); MessagePlugin.success("已删除"); }
    catch { MessagePlugin.error("删除失败"); }
  };

  // --- Import / Export / Reset ---
  const handleExport = async () => {
    try {
      const resp = await exportKeywords();
      const blob = await resp.blob();
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url; a.download = "miho_keywords.json"; a.click();
      URL.revokeObjectURL(url);
      MessagePlugin.success("关键词词典已导出");
    } catch { MessagePlugin.error("导出失败"); }
  };

  const handleImport = async (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    try {
      const text = await file.text();
      const data = JSON.parse(text);
      const items = data.keywords || data;
      if (!Array.isArray(items)) { MessagePlugin.error("JSON格式错误：需要 keywords 数组"); return; }
      const r = await importKeywords({ keywords: items, mode: "merge" });
      MessagePlugin.success(r.message);
      loadAll();
    } catch (err: any) { MessagePlugin.error(err?.message || "导入失败，请检查JSON格式"); }
    if (fileInputRef.current) fileInputRef.current.value = "";
  };

  const handleReset = async () => {
    try {
      const r = await resetKeywords();
      MessagePlugin.success(r.message);
      loadAll();
    } catch { MessagePlugin.error("重置失败"); }
  };

  // --- Category handlers ---
  const openCatDlg = (key?: string, name?: string) => {
    setCatEditKey(key || "");
    setCatEditName(name || "");
    setCatAddKey("");
    setCatAddName("");
    setCatDlg(true);
  };

  const handleCatAdd = async () => {
    if (!catAddKey.trim() || !catAddName.trim()) { MessagePlugin.warning("分类键和名称不能为空"); return; }
    try {
      await addCategory({ key: catAddKey.trim(), name: catAddName.trim() });
      setCatAddKey(""); setCatAddName("");
      loadAll(); MessagePlugin.success("分类已添加");
    } catch (e: any) { MessagePlugin.error(e?.message || "添加失败"); }
  };

  const handleCatRename = async () => {
    if (!catEditName.trim()) { MessagePlugin.warning("名称不能为空"); return; }
    try {
      await updateCategory(catEditKey, { name: catEditName.trim() });
      loadAll(); MessagePlugin.success("分类已更新");
    } catch { MessagePlugin.error("更新失败"); }
  };

  const handleCatDelete = async (key: string) => {
    try { await deleteCategory(key); loadAll(); MessagePlugin.success("分类已删除，关键词已迁移"); }
    catch (e: any) { MessagePlugin.error(e?.message || "删除失败"); }
  };

  const columns = [
    { colKey: "keyword", title: "关键词", cell: ({ row }: any) => <span className="text-white font-medium">{row.keyword}</span> },
    { colKey: "category", title: "分类", width: 140,
      cell: ({ row }: any) => {
        const cc = getCatColor(row.category);
        return <Tag style={{ backgroundColor: cc + "20", color: cc, border: "none" }} size="small">{catMap[row.category] || row.category}</Tag>;
      }
    },
    { colKey: "addedBy", title: "来源", width: 75, cell: ({ row }: any) => <Tag theme={row.addedBy === "system" ? "default" : "primary"} size="small" variant="light">{row.addedBy === "system" ? "系统" : "用户"}</Tag> },
    { colKey: "addedAt", title: "添加时间", width: 120, cell: ({ row }: any) => <span className="text-sm text-[#94a3b8]">{row.addedAt ? new Date(row.addedAt).toLocaleDateString("zh-CN") : "-"}</span> },
    { colKey: "actions", title: "操作", width: 120,
      cell: ({ row }: any) => (
        <div className="flex items-center gap-1">
          <Button variant="text" size="small" icon={<EditIcon />} onClick={() => openEdit(row)} title="编辑" />
          <Popconfirm content="确定删除？" onConfirm={() => handleDelete(row.id)}>
            <Button variant="text" theme="danger" size="small" icon={<DeleteIcon />} />
          </Popconfirm>
        </div>
      )
    },
  ];

  return (
    <div className="space-y-6 animate-fade-in-up">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-white">关键词词典</h1>
          <p className="text-sm text-[#94a3b8] mt-1">管理二游圈识别关键词库，支持编辑和分类管理</p>
        </div>
        <div className="flex gap-2">
          <Button variant="outline" icon={<DownloadIcon />} onClick={handleExport}>导出</Button>
          <Button variant="outline" icon={<UploadIcon />} onClick={() => fileInputRef.current?.click()}>导入</Button>
          <input type="file" ref={fileInputRef} onChange={handleImport} accept=".json" style={{ display: "none" }} />
          <Popconfirm content="确定重置为默认200+条关键词？" onConfirm={handleReset}>
            <Button variant="outline" icon={<RefreshIcon />}>重置</Button>
          </Popconfirm>
          <Button variant="outline" icon={<FolderAddIcon />} onClick={() => openCatDlg()}>管理分类</Button>
          <Button theme="primary" icon={<AddIcon />} onClick={() => setAddDlg(true)}>添加关键词</Button>
        </div>
      </div>

      <div className="flex items-center gap-4 flex-wrap">
        <Input prefixIcon={<SearchIcon />} placeholder="搜索关键词..." value={searchText} onChange={v => setSearchText(v as string)} style={{ width: 240 }} clearable />
        <Select value={filterCategory} onChange={v => setFilterCategory(v as string)} options={categoryOptions} style={{ width: 160 }} />
        <div className="flex-1" />
        <span className="text-sm text-[#94a3b8]">{filtered.length} / {keywords.length} 条</span>
      </div>

      <div className="grid grid-cols-2 md:grid-cols-3 lg:grid-cols-6 gap-3">
        {catList.map(({ key, name }) => {
          const count = keywords.filter(k => k.category === key).length;
          return <div key={key} className="glass-card p-3 text-center"><div className="text-xs text-[#94a3b8]">{name}</div><div className="text-xl font-bold text-white mt-1">{count}</div></div>;
        })}
      </div>

      <div className="glass-card p-5">
        <Table data={filtered} columns={columns} rowKey="id" size="medium" hover stripe bordered={false} loading={loading} empty="暂无匹配的关键词" pagination={{ defaultPageSize: 20, pageSizeOptions: [20, 50, 100], total: filtered.length, showJumper: true }} />
      </div>

      {/* Add Keyword Dialog */}
      <Dialog header="添加关键词" visible={addDlg} onClose={() => setAddDlg(false)} onConfirm={handleAdd} confirmBtn="确认添加" cancelBtn="取消" destroyOnClose>
        <div className="space-y-4 py-2">
          <div><label className="text-sm text-[#94a3b8] block mb-1">关键词</label><Input value={newKw} onChange={v => setNewKw(v as string)} placeholder="输入关键词" /></div>
          <div><label className="text-sm text-[#94a3b8] block mb-1">分类</label><Select value={newCat} onChange={v => setNewCat(v as string)} options={catEditOptions} style={{ width: "100%" }} /></div>
        </div>
      </Dialog>

      {/* Edit Keyword Dialog */}
      <Dialog header="编辑关键词" visible={editDlg} onClose={() => setEditDlg(false)} onConfirm={handleEdit} confirmBtn="保存" cancelBtn="取消" destroyOnClose>
        <div className="space-y-4 py-2">
          <div><label className="text-sm text-[#94a3b8] block mb-1">关键词名称</label><Input value={editKw} onChange={v => setEditKw(v as string)} placeholder="关键词" /></div>
          <div><label className="text-sm text-[#94a3b8] block mb-1">分类</label><Select value={editCat} onChange={v => setEditCat(v as string)} options={catEditOptions} style={{ width: "100%" }} /></div>
        </div>
      </Dialog>

      {/* Category Management Dialog */}
      <Dialog header="分类管理" visible={catDlg} onClose={() => setCatDlg(false)} confirmBtn={null} cancelBtn="关闭" width={520} destroyOnClose>
        <div className="space-y-4 py-2">
          {/* Add new category */}
          <div className="p-3 rounded-lg bg-[#1a1a2e] border border-[#334155]">
            <p className="text-sm font-semibold text-white mb-2">新建分类</p>
            <div className="flex gap-2">
              <Input value={catAddKey} onChange={v => setCatAddKey(v as string)} placeholder="键（英文ID）" style={{ flex: 1 }} />
              <Input value={catAddName} onChange={v => setCatAddName(v as string)} placeholder="显示名称" style={{ flex: 1 }} />
              <Button theme="primary" size="small" onClick={handleCatAdd}>添加</Button>
            </div>
          </div>

          {/* Existing categories */}
          <div>
            <p className="text-sm font-semibold text-white mb-2">已有分类</p>
            <div className="space-y-1 max-h-64 overflow-y-auto">
              {catList.map(({ key, name }) => (
                <div key={key} className="flex items-center gap-2 p-2 rounded hover:bg-[#1a1a2e]">
                  <Tag style={{ backgroundColor: getCatColor(key) + "20", color: getCatColor(key), border: "none" }} size="small">{key}</Tag>
                  <span className="text-sm text-[#e2e8f0] flex-1">{name}</span>
                  <span className="text-xs text-[#64748b]">({keywords.filter(k => k.category === key).length} 词)</span>
                  {catEditKey === key ? (
                    <>
                      <Input value={catEditName} onChange={v => setCatEditName(v as string)} size="small" style={{ width: 120 }} />
                      <Button variant="text" size="small" theme="primary" onClick={handleCatRename}>保存</Button>
                      <Button variant="text" size="small" onClick={() => { setCatEditKey(""); setCatEditName(""); }}>取消</Button>
                    </>
                  ) : (
                    <>
                      <Button variant="text" size="small" icon={<EditIcon />} onClick={() => openCatDlg(key, name)} title="重命名" />
                      <Popconfirm content={`删除分类 "${name}"？关键词将迁移到其他分类`} onConfirm={() => handleCatDelete(key)}>
                        <Button variant="text" theme="danger" size="small" icon={<DeleteIcon />} />
                      </Popconfirm>
                    </>
                  )}
                </div>
              ))}
            </div>
          </div>
        </div>
      </Dialog>
    </div>
  );
}
