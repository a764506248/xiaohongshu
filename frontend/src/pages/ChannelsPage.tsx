import { useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { contentApi } from "../api/content";
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
    await contentApi.createAccount({
      name: `${active === "wechat" ? "公众号" : "小红书"}演示账号`,
      channel: active,
      mode: "manual",
      credential_reference: "",
    });
    await load();
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
      {!!variants.length && (
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
          {current && (
            <section className="workspace">
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
              <aside className="panel">
                <h2>发布账号</h2>
                {accounts
                  .filter((a) => a.channel === active)
                  .map((a) => (
                    <div className="history-row" key={a.id}>
                      <strong>{a.name}</strong>
                      <span>
                        {a.mode === "manual" ? "人工发布" : "模拟发布"}
                      </span>
                      {can("publish:execute") && <button
                        className="button secondary"
                        onClick={() => schedule(a)}
                      >
                        创建发布任务
                      </button>}
                    </div>
                  ))}
                <button className="button secondary" onClick={addAccount}>
                  ＋ 添加人工账号
                </button>
                {active === "wechat" && (
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
          )}
        </>
      )}
    </main>
  );
}
