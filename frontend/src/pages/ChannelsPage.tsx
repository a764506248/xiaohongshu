import { useEffect, useRef, useState } from "react";
import { Modal, Spin } from "antd";
import { Link, useParams } from "react-router-dom";
import { contentApi } from "../api/content";
import { ApiError } from "../api/client";
import { useAuth } from "../auth";
import { Notice } from "../components/Notice";
import type { ChannelAccount, ChannelVariant } from "../types";
export function ChannelsPage() {
  const { can } = useAuth();
  const { id = "" } = useParams();
  const [variants, setVariants] = useState<ChannelVariant[]>([]);
  const [accounts, setAccounts] = useState<ChannelAccount[]>([]);
  const [active, setActive] = useState("xiaohongshu");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [accountName, setAccountName] = useState("小红书运营账号");
  const [accountMode, setAccountMode] = useState<"manual" | "xhs_mcp">("manual");
  const [accountReference, setAccountReference] = useState("");
  const [loginSession, setLoginSession] = useState<{ id: string; status: string; message: string; qrUrl?: string } | null>(null);
  const loginTimer = useRef<number | null>(null);
  useEffect(() => () => { if (loginTimer.current) window.clearTimeout(loginTimer.current); }, []);
  const load = async () => {
    setVariants(await contentApi.getVariants(id));
    setAccounts(await contentApi.listAccounts());
  };
  useEffect(() => {
    load().catch((e) => setError(e.message));
  }, [id]);
  const current = variants.find((v) => v.channel === active);
  const mutate = (data: Partial<ChannelVariant>) =>
    setVariants(
      variants.map((v) => (v.id === current?.id ? { ...v, ...data } : v)),
    );
  async function generate() {
    try {
      setVariants(await contentApi.createVariants(id));
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function save() {
    if (current) {
      await contentApi.updateVariant(current.id, {
        title: current.title,
        summary: current.summary,
        body: current.body,
        tags: current.tags,
        cover_url: current.cover_url,
      });
      await load();
    }
  }
  async function addAccount() {
    setError("");
    try {
      await contentApi.createAccount({
        name: accountName.trim() || `${active === "wechat" ? "公众号" : "小红书"}账号`,
        channel: active,
        mode: active === "xiaohongshu" ? accountMode : "manual",
        credential_reference: accountReference.trim(),
      });
      setNotice("发布账号已添加");
      await load();
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function checkAccount(account: ChannelAccount) {
    setError("");
    try {
      const result = await contentApi.accountConnectionStatus(account.id);
      if (result.status === "logged_in") {
        setNotice(result.message);
        return;
      }
      const session = await contentApi.createAccountLoginSession(account.id);
      setLoginSession({ id: session.session_id, status: session.status, message: session.message });
      // 浏览器子进程需要一点启动时间，避免创建完成后立即轮询产生瞬时 404。
      loginTimer.current = window.setTimeout(() => pollLogin(session.session_id, account), 500);
    } catch (e) {
      setError((e as Error).message);
    }
  }
  async function pollLogin(sessionId: string, account: ChannelAccount, missingRetries = 0) {
    try {
      const result = await contentApi.getXhsLoginSession(sessionId);
      setLoginSession({ id: sessionId, status: result.status, message: result.message, qrUrl: result.qr_image });
      if (result.status === "logged_in") {
        const checked = await contentApi.accountConnectionStatus(account.id);
        setNotice(checked.message);
        loginTimer.current = window.setTimeout(() => setLoginSession(null), 900);
      } else if (result.status !== "failed") {
        loginTimer.current = window.setTimeout(() => pollLogin(sessionId, account), 1500);
      }
    } catch (e) {
      // 登录会话刚创建时，文件系统或热更新进程可能短暂尚不可见。
      // 最多容忍约 10 秒的 404，避免把可恢复的启动竞态展示成永久失败。
      if (e instanceof ApiError && e.status === 404 && missingRetries < 6) {
        setLoginSession((value) => value ? { ...value, status: "starting", message: "正在初始化登录会话…" } : null);
        loginTimer.current = window.setTimeout(
          () => pollLogin(sessionId, account, missingRetries + 1),
          1500,
        );
        return;
      }
      setLoginSession((value) => value ? { ...value, status: "failed", message: (e as Error).message } : null);
    }
  }
  async function schedule(account: ChannelAccount) {
    if (current) {
      await contentApi.createPublishJob({
        channel_variant_id: current.id,
        channel_account_id: account.id,
        idempotency_key: crypto.randomUUID(),
        scheduled_at: null,
        max_retries: 3,
      });
      location.href = "/publishing";
    }
  }
  return (
    <main>
      <Link className="back" to={`/tasks/${id}`}>
        ← 返回任务
      </Link>
      <div className="page-heading">
        <div>
          <p className="eyebrow">PHASE 3</p>
          <h1>多平台内容与账号</h1>
          <p>同一终稿分别维护小红书和微信公众号版本。</p>
        </div>
        {!variants.length && (
          <button className="button primary" onClick={generate}>
            生成平台版本
          </button>
        )}
      </div>
      {error && <Notice>{error}</Notice>}
      {notice && <Notice type="success">{notice}</Notice>}
      <Modal
        title="登录小红书账号"
        open={!!loginSession}
        footer={null}
        destroyOnHidden
        onCancel={() => { if (loginTimer.current) window.clearTimeout(loginTimer.current); setLoginSession(null); }}
      >
        <div className="xhs-login-modal">
          {loginSession?.qrUrl ? (
            <img src={loginSession.qrUrl} alt="小红书登录二维码" />
          ) : loginSession?.status === "failed" ? null : <Spin size="large" />}
          <p>{loginSession?.message}</p>
          {loginSession?.status === "waiting_scan" && <small>请使用小红书 App 扫码，登录成功后页面会自动关闭。</small>}
        </div>
      </Modal>
      <>
          <div className="tabs">
            <button
              onClick={() => setActive("xiaohongshu")}
              className={active === "xiaohongshu" ? "active" : ""}
            >
              小红书
            </button>
            <button
              onClick={() => setActive("wechat")}
              className={active === "wechat" ? "active" : ""}
            >
              微信公众号
            </button>
          </div>
          <section className="workspace">
            {current ? (
              <div className="panel editor">
                <label>
                  标题
                  <input
                    value={current.title}
                    onChange={(e) => mutate({ title: e.target.value })}
                  />
                </label>
                <label>
                  摘要
                  <textarea
                    rows={3}
                    value={current.summary}
                    onChange={(e) => mutate({ summary: e.target.value })}
                  />
                </label>
                <label>
                  正文
                  <textarea
                    className="article-editor"
                    value={current.body}
                    onChange={(e) => mutate({ body: e.target.value })}
                  />
                </label>
                <label>
                  标签
                  <input
                    value={current.tags}
                    onChange={(e) => mutate({ tags: e.target.value })}
                  />
                </label>
                <button className="button primary" onClick={save}>
                  保存平台版本
                </button>
              </div>
            ) : (
              <div className="panel centered">
                <h2>尚未生成平台内容</h2>
                <p>发布账号已经保存。请先生成平台版本，再编辑内容或创建发布任务。</p>
                <button className="button primary" onClick={generate}>
                  生成平台版本
                </button>
              </div>
            )}
              <aside className="panel">
                <h2>发布账号</h2>
                {accounts.filter((a) => a.channel === active).length === 0 && (
                  <p className="empty">当前平台还没有发布账号</p>
                )}
                {accounts.filter((a) => a.channel === active)
                  .map((a) => (
                    <div className="history-row" key={a.id}>
                      <strong>{a.name}</strong>
                      <span>
                        {a.mode === "manual"
                          ? "人工发布"
                          : a.mode === "xhs_mcp"
                            ? "XHS MCP 自动发布"
                            : "模拟发布"}
                      </span>
                      {a.mode === "xhs_mcp" && can("publish:execute") && (
                        <button
                          className="button secondary"
                          onClick={() => checkAccount(a)}
                        >
                          检测登录
                        </button>
                      )}
                      {current && can("publish:execute") && <button
                        className="button secondary"
                        onClick={() => schedule(a)}
                      >
                        创建发布任务
                      </button>}
                    </div>
                  ))}
                <div className="channel-account-form">
                  <h3>添加发布账号</h3>
                  <label>
                    账号名称
                    <input
                      value={accountName}
                      onChange={(event) => setAccountName(event.target.value)}
                      placeholder="例如：小红书 4141741101"
                    />
                  </label>
                  {active === "xiaohongshu" && (
                    <label>
                      发布方式
                      <select
                        value={accountMode}
                        onChange={(event) =>
                          setAccountMode(event.target.value as "manual" | "xhs_mcp")
                        }
                      >
                        <option value="manual">人工发布</option>
                        <option value="xhs_mcp">XHS MCP 自动发布</option>
                      </select>
                    </label>
                  )}
                  <label>
                    账号标识（可选）
                    <input
                      value={accountReference}
                      onChange={(event) => setAccountReference(event.target.value)}
                      placeholder="小红书号或 MCP 账号别名"
                    />
                  </label>
                  <button className="button secondary" onClick={addAccount}>
                    ＋ 添加账号
                  </button>
                </div>
                {active === "wechat" && current && (
                  <>
                    <h3>富文本预览</h3>
                    <div
                      className="html-preview"
                      dangerouslySetInnerHTML={{ __html: current.html_content }}
                    />
                  </>
                )}
              </aside>
            </section>
        </>
    </main>
  );
}
