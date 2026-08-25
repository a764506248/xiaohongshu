import { api } from './client'
import type { Article, ArticleVersion, ContentTask, Review, Topic } from '../types'

export const contentApi = {
  listTasks: () => api<ContentTask[]>('/content-tasks'),
  getTask: (id: string) => api<ContentTask>(`/content-tasks/${id}`),
  createTask: (data: { title: string; requirement: string; target_audience: string }) =>
    api<ContentTask>('/content-tasks', { method: 'POST', body: JSON.stringify(data) }),
  generateTopics: (id: string, instruction = '') =>
    api(`/content-tasks/${id}/generate-topics`, { method: 'POST', body: JSON.stringify({ instruction }) }),
  getTopics: (id: string) => api<Topic[]>(`/content-tasks/${id}/topics`),
  selectTopic: (id: string, topicId: string) =>
    api(`/content-tasks/${id}/select-topic`, { method: 'POST', body: JSON.stringify({ topic_id: topicId }) }),
  getArticle: (id: string) => api<Article>(`/content-tasks/${id}/article`),
  saveVersion: (articleId: string, title: string, content: string) =>
    api<ArticleVersion>(`/articles/${articleId}/versions`, { method: 'POST', body: JSON.stringify({ title, content }) }),
  review: (id: string, data: Record<string, unknown>) =>
    api<Review>(`/content-tasks/${id}/review`, { method: 'POST', body: JSON.stringify(data) }),
  getReviews: (id: string) => api<Review[]>(`/content-tasks/${id}/reviews`),
}

