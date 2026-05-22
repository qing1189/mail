// MS Mail Reg Tool - Web Console (Alpine.js)

const api = {
  async get(url) {
    const r = await fetch(url, { credentials: "same-origin" });
    if (r.status === 401) throw new Error("UNAUTHENTICATED");
    return r.json();
  },
  async send(url, method, body) {
    const r = await fetch(url, {
      method,
      credentials: "same-origin",
      headers: { "Content-Type": "application/json" },
      body: body ? JSON.stringify(body) : undefined,
    });
    if (r.status === 401) throw new Error("UNAUTHENTICATED");
    const text = await r.text();
    let json = null;
    try { json = text ? JSON.parse(text) : {}; } catch (_) { json = { _raw: text }; }
    if (!r.ok) {
      const detail = (json && json.detail) || `HTTP ${r.status}`;
      throw new Error(typeof detail === "string" ? detail : JSON.stringify(detail));
    }
    return json;
  },
  post(url, body) { return this.send(url, "POST", body); },
  put(url, body) { return this.send(url, "PUT", body); },
  del(url) { return this.send(url, "DELETE"); },
};

// ── 全局认证状态(被两个 Alpine 组件共享) ──────────────────────
const authState = {
  authed: false,
  setupRequired: false,
  listeners: [],
  set(value, setupRequired) {
    this.authed = value;
    this.setupRequired = setupRequired ?? this.setupRequired;
    this.listeners.forEach(fn => { try { fn(this); } catch (_) {} });
  },
  subscribe(fn) { this.listeners.push(fn); return () => { this.listeners = this.listeners.filter(f => f !== fn); }; },
};

async function refreshAuthStatus() {
  try {
    const data = await api.get("/api/auth/status");
    authState.set(!!data.authenticated, !!data.setup_required);
  } catch (_) {
    authState.set(false, false);
  }
}

// ── 登录 / 设置密码组件 ────────────────────────────────────────
function loginApp() {
  return {
    authed: false,
    setupRequired: false,
    password: "",
    password2: "",
    error: "",
    loading: false,
    init() {
      this.authed = authState.authed;
      this.setupRequired = authState.setupRequired;
      authState.subscribe((s) => {
        this.authed = s.authed;
        this.setupRequired = s.setupRequired;
      });
      refreshAuthStatus();
    },
    async submit() {
      this.error = "";
      if (!this.password) { this.error = "请输入密码"; return; }
      this.loading = true;
      try {
        if (this.setupRequired) {
          if (this.password !== this.password2) {
            this.error = "两次输入的密码不一致";
            this.loading = false;
            return;
          }
          await api.post("/api/auth/setup", { password: this.password });
          await api.post("/api/auth/login", { password: this.password });
        } else {
          await api.post("/api/auth/login", { password: this.password });
        }
        this.password = "";
        this.password2 = "";
        await refreshAuthStatus();
      } catch (e) {
        this.error = e.message || "登录失败";
      } finally {
        this.loading = false;
      }
    },
  };
}

// ── 主应用组件 ──────────────────────────────────────────────────
function mainApp() {
  return {
    authed: false,
    leftTab: "config",

    // config
    cfg: {
      email_suffix: "@outlook.com",
      proxy_source: "api",
      proxy_file: "proxies.txt",
      proxy_api_url: "",
      proxy_api_timeout: 8,
      proxy_test_timeout: 8,
      proxy_test_urls: [],
      bot_protection_wait: 11,
      max_captcha_retries: 2,
      concurrent_flows: 10,
      max_tasks: 20,
      oauth2: { enable_oauth2: false, client_id: "", redirect_url: "", Scopes: [] },
      ruyipage: { browser_path: "", profile_root: "Profiles", headless: false, xpath_picker: false, action_visual: false },
    },
    scopesText: "",
    testUrlsText: "",
    cfgSaving: false,
    cfgMsg: "",

    // proxy file
    proxyFile: { path: "proxies.txt", content: "", proxy_source: "" },
    proxySaving: false,
    proxyFileMsg: "",

    // proxy test
    proxyTest: {
      source: "current",
      limit: 10,
      concurrency: 5,
      running: false,
      results: [],
      summary: "",
    },

    // batches
    batches: [],
    newBatch: { label: "", concurrent_flows: null, max_tasks: null, email_suffix: "", proxy_source: "", inline_proxies: "" },
    batchSubmitting: false,
    batchMsg: "",

    // logs / ws
    logs: [],
    autoscroll: true,
    ws: null,
    wsStatus: { text: "未连接", cls: "" },

    // change password
    changePasswordModal: false,
    cp: { old: "", new: "", loading: false, error: "" },

    // results
    results: {},

    // ── lifecycle ────────────────────────────────────────────
    init() {
      this.authed = authState.authed;
      authState.subscribe((s) => {
        const wasAuthed = this.authed;
        this.authed = s.authed;
        if (this.authed && !wasAuthed) {
          this.bootstrap();
        }
      });
      if (this.authed) this.bootstrap();
    },

    async bootstrap() {
      await this.loadConfig();
      await this.loadBatches();
      await this.reloadProxyFile();
      await this.loadResults();
      this.connectWs();
    },

    // ── ws ───────────────────────────────────────────────────
    connectWs() {
      if (this.ws) return;
      const proto = location.protocol === "https:" ? "wss:" : "ws:";
      const url = `${proto}//${location.host}/ws/events`;
      this.wsStatus = { text: "连接中…", cls: "" };
      const ws = new WebSocket(url);
      this.ws = ws;
      ws.onopen = () => { this.wsStatus = { text: "● 已连接", cls: "success" }; };
      ws.onclose = () => {
        this.wsStatus = { text: "● 已断开", cls: "error" };
        this.ws = null;
        setTimeout(() => { if (this.authed) this.connectWs(); }, 2000);
      };
      ws.onerror = () => { this.wsStatus = { text: "● 错误", cls: "error" }; };
      ws.onmessage = (ev) => {
        try {
          const env = JSON.parse(ev.data);
          this.handleWsEvent(env);
        } catch (_) {}
      };
    },

    handleWsEvent(env) {
      const type = env.type;
      const data = env.data;
      if (type === "history") {
        for (const item of data) {
          if (item.type === "log") this.appendLog(item.data);
        }
        this.scrollLogsToBottom();
      } else if (type === "log") {
        this.appendLog(data);
        if (this.autoscroll) this.scrollLogsToBottom();
      } else if (type === "batch_snapshot") {
        this.batches = data || [];
      } else if (type === "batch_added" || type === "batch_updated") {
        this.applyBatchUpdate(data);
        // 如果批次结束,刷新结果文件计数
        if (["completed", "cancelled", "failed"].includes(data.status)) {
          this.loadResults();
        }
      }
    },

    appendLog(entry) {
      this.logs.push(entry);
      if (this.logs.length > 800) this.logs.splice(0, this.logs.length - 800);
    },

    applyBatchUpdate(b) {
      const idx = this.batches.findIndex(x => x.id === b.id);
      if (idx >= 0) this.batches.splice(idx, 1, b);
      else this.batches.unshift(b);
    },

    scrollLogsToBottom() {
      this.$nextTick(() => {
        const box = this.$refs.logBox;
        if (box) box.scrollTop = box.scrollHeight;
      });
    },

    clearLogs() { this.logs = []; },

    // ── auth ─────────────────────────────────────────────────
    async logout() {
      try { await api.post("/api/auth/logout"); } catch (_) {}
      if (this.ws) { try { this.ws.close(); } catch (_) {} this.ws = null; }
      authState.set(false, false);
      this.logs = [];
      this.batches = [];
    },

    async submitChangePassword() {
      this.cp.error = "";
      if (!this.cp.old || !this.cp.new) { this.cp.error = "请输入旧密码和新密码"; return; }
      this.cp.loading = true;
      try {
        await api.post("/api/auth/change-password", { old_password: this.cp.old, new_password: this.cp.new });
        this.changePasswordModal = false;
        this.cp = { old: "", new: "", loading: false, error: "" };
        await this.logout();
      } catch (e) {
        this.cp.error = e.message;
      } finally {
        this.cp.loading = false;
      }
    },

    // ── config ───────────────────────────────────────────────
    async loadConfig() {
      try {
        const data = await api.get("/api/config");
        this.cfg = data;
        if (!this.cfg.oauth2) this.cfg.oauth2 = { enable_oauth2: false, client_id: "", redirect_url: "", Scopes: [] };
        if (!this.cfg.ruyipage) this.cfg.ruyipage = { browser_path: "", profile_root: "Profiles", headless: false };
        this.scopesText = (this.cfg.oauth2.Scopes || []).join("\n");
        this.testUrlsText = (this.cfg.proxy_test_urls || []).join("\n");
      } catch (e) {
        if (e.message === "UNAUTHENTICATED") authState.set(false);
        this.cfgMsg = "加载失败: " + e.message;
      }
    },

    async saveConfig() {
      this.cfgSaving = true;
      this.cfgMsg = "";
      try {
        const payload = JSON.parse(JSON.stringify(this.cfg));
        payload.oauth2.Scopes = this.scopesText.split("\n").map(s => s.trim()).filter(Boolean);
        payload.proxy_test_urls = this.testUrlsText.split("\n").map(s => s.trim()).filter(Boolean);
        // 不要把脱敏后的 web 字段写回去
        delete payload.web;
        await api.put("/api/config", payload);
        this.cfgMsg = "✓ 已保存";
        setTimeout(() => this.cfgMsg = "", 2000);
      } catch (e) {
        this.cfgMsg = "✗ 保存失败: " + e.message;
      } finally {
        this.cfgSaving = false;
      }
    },

    // ── proxy file ───────────────────────────────────────────
    async reloadProxyFile() {
      try {
        const data = await api.get("/api/proxies/file");
        this.proxyFile = data;
      } catch (e) {
        this.proxyFileMsg = "加载失败: " + e.message;
      }
    },

    async saveProxyFile() {
      this.proxySaving = true;
      this.proxyFileMsg = "";
      try {
        const r = await api.put("/api/proxies/file", { content: this.proxyFile.content });
        this.proxyFileMsg = `✓ 已保存 (${r.bytes} 字节)`;
        setTimeout(() => this.proxyFileMsg = "", 2000);
      } catch (e) {
        this.proxyFileMsg = "✗ 保存失败: " + e.message;
      } finally {
        this.proxySaving = false;
      }
    },

    async uploadProxyFile(ev) {
      const file = ev.target.files[0];
      if (!file) return;
      const fd = new FormData();
      fd.append("file", file);
      try {
        const r = await fetch("/api/proxies/upload", { method: "POST", body: fd, credentials: "same-origin" });
        if (!r.ok) throw new Error(await r.text());
        const j = await r.json();
        this.proxyFileMsg = `✓ 已上传 ${j.filename}`;
        await this.reloadProxyFile();
      } catch (e) {
        this.proxyFileMsg = "✗ 上传失败: " + e.message;
      } finally {
        ev.target.value = "";
      }
    },

    async deleteProxyFile() {
      if (!confirm("确认删除 proxies.txt? 文件会从磁盘移除,编辑器内容会被清空。")) return;
      this.proxySaving = true;
      this.proxyFileMsg = "";
      try {
        const r = await api.del("/api/proxies/file");
        this.proxyFile.content = "";
        this.proxyFile.exists = false;
        this.proxyFileMsg = r.existed ? "✓ 文件已删除" : "(文件原本就不存在)";
        setTimeout(() => this.proxyFileMsg = "", 2500);
      } catch (e) {
        this.proxyFileMsg = "✗ 删除失败: " + e.message;
      } finally {
        this.proxySaving = false;
      }
    },

    async runProxyTest() {
      this.proxyTest.running = true;
      this.proxyTest.results = [];
      this.proxyTest.summary = "";
      try {
        const payload = {
          source: this.proxyTest.source,
          limit: this.proxyTest.limit,
          concurrency: this.proxyTest.concurrency,
        };
        if (this.proxyTest.source === "inline") payload.inline_text = this.proxyFile.content;
        const r = await api.post("/api/proxies/test", payload);
        this.proxyTest.results = r.results || [];
        this.proxyTest.summary = `共加载 ${r.total} 条 · 测试 ${r.tested} 条 · 通过 ${r.passed} 条`;
      } catch (e) {
        this.proxyTest.summary = "测试失败: " + e.message;
      } finally {
        this.proxyTest.running = false;
      }
    },

    // ── batches ──────────────────────────────────────────────
    async loadBatches() {
      try {
        const r = await api.get("/api/batches");
        this.batches = r.batches || [];
      } catch (_) {}
    },

    async submitBatch() {
      this.batchSubmitting = true;
      this.batchMsg = "";
      try {
        const payload = { label: this.newBatch.label || undefined };
        if (this.newBatch.concurrent_flows) payload.concurrent_flows = this.newBatch.concurrent_flows;
        if (this.newBatch.max_tasks) payload.max_tasks = this.newBatch.max_tasks;
        if (this.newBatch.email_suffix) payload.email_suffix = this.newBatch.email_suffix;
        if (this.newBatch.proxy_source) payload.proxy_source = this.newBatch.proxy_source;
        if (this.newBatch.inline_proxies && this.newBatch.inline_proxies.trim()) {
          payload.inline_proxies = this.newBatch.inline_proxies;
        }
        await api.post("/api/batches", payload);
        this.batchMsg = "✓ 已加入队列";
        this.newBatch = { label: "", concurrent_flows: null, max_tasks: null, email_suffix: "", proxy_source: "", inline_proxies: "" };
        setTimeout(() => this.batchMsg = "", 2000);
      } catch (e) {
        this.batchMsg = "✗ 失败: " + e.message;
      } finally {
        this.batchSubmitting = false;
      }
    },

    copyCurrentProxiesToBatch() {
      this.newBatch.inline_proxies = this.proxyFile.content || "";
      this.batchMsg = this.newBatch.inline_proxies
        ? `✓ 已拷贝当前 proxies.txt (${this.newBatch.inline_proxies.split('\n').filter(s => s.trim()).length} 行)`
        : "(当前 proxies.txt 为空)";
      setTimeout(() => this.batchMsg = "", 2500);
    },

    async cancelBatch(id) {
      if (!confirm("确认取消该批次?")) return;
      try { await api.del(`/api/batches/${id}`); }
      catch (e) { alert("取消失败: " + e.message); }
    },

    async stopAll() {
      if (!confirm("确认停止全部批次? 排队中的会被取消,运行中的会等线程跑完后停止。")) return;
      try { await api.post("/api/batches/stop-all"); }
      catch (e) { alert("停止失败: " + e.message); }
    },

    // ── results ──────────────────────────────────────────────
    async loadResults() {
      try { this.results = await api.get("/api/results"); }
      catch (_) {}
    },

    downloadUrl(name) { return `/api/results/${name}/download`; },

    // ── helpers ──────────────────────────────────────────────
    currentBatch() {
      return this.batches.find(b => b.status === "running" || b.status === "stopping");
    },

    progressPercent() {
      const b = this.currentBatch();
      if (!b || !b.stats.total) return 0;
      const done = b.stats.succeeded + b.stats.failed;
      return Math.min(100, (done / b.stats.total * 100));
    },

    successRate() {
      const b = this.currentBatch();
      if (!b) return "-";
      const done = b.stats.succeeded + b.stats.failed;
      if (!done) return "-";
      return (b.stats.succeeded / done * 100).toFixed(1) + "%";
    },

    badgeClass(status) {
      switch (status) {
        case "running": return "running";
        case "completed": return "success";
        case "failed":
        case "cancelled": return "error";
        case "stopping": return "warn";
        default: return "";
      }
    },

    formatTime(ts) {
      if (!ts) return "-";
      const d = new Date(ts * 1000);
      return d.toLocaleTimeString("zh-CN", { hour12: false });
    },
  };
}
