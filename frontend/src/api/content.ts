import {
  api,
  API_BASE,
  streamApi,
  uploadApi,
  type StreamEvent,
} from "./client";
import type {
  AnalyticsSummary,
  Article,
  ArticleVersion,
  ChannelAccount,
  ChannelVariant,
  ContentTask,
  ImagePage,
  ImageVersion,
  ModelUsage,
  PublishJob,
  Review,
  TokenUsageReport,
  Topic,
  XiaohongshuPackage,
} from "../types";

export const contentApi = {
  listTasks: () => api<ContentTask[]>("/content-tasks"),
  getTask: (id: string) => api<ContentTask>(`/content-tasks/${id}`),
  createTask: (data: {
    title: string;
    requirement: string;
    target_audience: string;
  }) =>
    api<ContentTask>("/content-tasks", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  generateTopics: (id: string, instruction = "") =>
    api(`/content-tasks/${id}/generate-topics`, {
      method: "POST",
      body: JSON.stringify({ instruction }),
    }),
  generateTopicsStream: (
    id: string,
    instruction: string,
    onEvent: (event: StreamEvent) => void,
  ) =>
    streamApi(
      `/content-tasks/${id}/generate-topics/stream`,
      { instruction },
      onEvent,
    ),
  getTopics: (id: string) => api<Topic[]>(`/content-tasks/${id}/topics`),
  selectTopic: (id: string, topicId: string) =>
    api(`/content-tasks/${id}/select-topic`, {
      method: "POST",
      body: JSON.stringify({ topic_id: topicId }),
    }),
  selectTopicStream: (
    id: string,
    topicId: string,
    onEvent: (event: StreamEvent) => void,
  ) =>
    streamApi(
      `/content-tasks/${id}/select-topic/stream`,
      { topic_id: topicId },
      onEvent,
    ),
  getArticle: (id: string) => api<Article>(`/content-tasks/${id}/article`),
  saveVersion: (articleId: string, title: string, content: string) =>
    api<ArticleVersion>(`/articles/${articleId}/versions`, {
      method: "POST",
      body: JSON.stringify({ title, content }),
    }),
  review: (id: string, data: Record<string, unknown>) =>
    api<Review>(`/content-tasks/${id}/review`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  getReviews: (id: string) => api<Review[]>(`/content-tasks/${id}/reviews`),
  createPackage: (id: string) =>
    api<XiaohongshuPackage>(`/content-tasks/${id}/xiaohongshu-package`, {
      method: "POST",
    }),
  getPackage: (id: string) =>
    api<XiaohongshuPackage>(`/content-tasks/${id}/xiaohongshu-package`),
  updatePackage: (
    id: string,
    data: { title: string; body: string; tags: string },
  ) =>
    api<XiaohongshuPackage>(`/content-tasks/${id}/xiaohongshu-package`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  updateImagePage: (
    pageId: string,
    data: { title: string; body: string; template: string },
  ) =>
    api<ImagePage>(`/image-pages/${pageId}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  regenerateImage: (pageId: string) =>
    api<ImageVersion>(`/image-pages/${pageId}/regenerate`, { method: "POST" }),
  uploadImage: (pageId: string, file: File) =>
    uploadApi<ImageVersion>(`/image-pages/${pageId}/upload`, file),
  reorderPages: (id: string, pageIds: string[]) =>
    api<XiaohongshuPackage>(
      `/content-tasks/${id}/xiaohongshu-package/page-order`,
      { method: "PUT", body: JSON.stringify({ page_ids: pageIds }) },
    ),
  exportUrl: (id: string) =>
    `${API_BASE}/content-tasks/${id}/xiaohongshu-package/export`,
  getVariants: (id: string) =>
    api<ChannelVariant[]>(`/content-tasks/${id}/channel-variants`),
  createVariants: (id: string) =>
    api<ChannelVariant[]>(`/content-tasks/${id}/channel-variants`, {
      method: "POST",
    }),
  updateVariant: (id: string, data: Partial<ChannelVariant>) =>
    api<ChannelVariant>(`/channel-variants/${id}`, {
      method: "PATCH",
      body: JSON.stringify(data),
    }),
  listAccounts: () => api<ChannelAccount[]>("/channel-accounts"),
  createAccount: (data: {
    name: string;
    channel: string;
    mode: string;
    credential_reference: string;
  }) =>
    api<ChannelAccount>("/channel-accounts", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  createPublishJob: (data: Record<string, unknown>) =>
    api<PublishJob>("/publish-jobs", {
      method: "POST",
      body: JSON.stringify(data),
    }),
  listPublishJobs: () => api<PublishJob[]>("/publish-jobs"),
  decidePublishJob: (id: string, decision: string, comment = "") =>
    api<PublishJob>(`/publish-jobs/${id}/decision`, {
      method: "POST",
      body: JSON.stringify({ decision, comment }),
    }),
  executePublishJob: (id: string) =>
    api<PublishJob>(`/publish-jobs/${id}/execute`, { method: "POST" }),
  retryPublishJob: (id: string) =>
    api<PublishJob>(`/publish-jobs/${id}/retry`, { method: "POST" }),
  completeManual: (id: string, external_post_id: string) =>
    api<PublishJob>(`/publish-jobs/${id}/complete-manual`, {
      method: "POST",
      body: JSON.stringify({ external_post_id }),
    }),
  addMetric: (id: string, data: Record<string, number>) =>
    api(`/publish-jobs/${id}/metrics`, {
      method: "POST",
      body: JSON.stringify(data),
    }),
  analytics: () => api<AnalyticsSummary>("/analytics/summary"),
  modelUsage: () => api<ModelUsage[]>("/analytics/model-usage"),
  tokenUsage: (
    startAt: string,
    endAt: string,
    granularity: "day" | "month" | "year",
  ) =>
    api<TokenUsageReport>(
      `/analytics/token-usage?start_at=${encodeURIComponent(startAt)}&end_at=${encodeURIComponent(endAt)}&granularity=${granularity}`,
    ),
};
