import request from '@/utils/request'

export interface ProjectPayload {
  id?: number
  name: string
  project_path: string
  save_mode: string
  created_at: string
  updated_at: string
  last_opened_at?: string
  /** B29：null = 从未真实保存过；非 null = 最近一次写盘时刻 */
  saved_at?: string | null
  /** null = 面板可见；非 null = 被「不保存」放弃，面板隐藏（磁盘文件保留作备份） */
  discarded_at?: string | null
}

export const createProject = (name?: string, projectPath?: string) =>
  request.post<unknown, { project: ProjectPayload }>('/projects', {
    name,
    project_path: projectPath,
  })

export const getRecentProjects = (limit = 8) =>
  request.get<unknown, { items: ProjectPayload[] }>(`/projects/recent?limit=${limit}`)

export const getProject = (projectId: number) =>
  request.get<unknown, { project: ProjectPayload }>(`/projects/${projectId}`)

/** B29：「不保存」放弃从未保存过的工程：面板软删除，磁盘文件不动 */
export const discardProject = (projectId: number) =>
  request.post<unknown, { project: ProjectPayload }>(`/projects/${projectId}/discard`)

/** B29：前端真实写盘成功后上报（自动保存 tick / 用户显式保存） */
export const markProjectSaved = (projectId: number) =>
  request.post<unknown, { project: ProjectPayload }>(`/projects/${projectId}/saved`)

/** B29：真实打开时刻上报：刷新面板排序 + 被放弃（但保存过）的工程复活 */
export const touchProjectOpened = (projectId: number) =>
  request.post<unknown, { project: ProjectPayload }>(`/projects/${projectId}/opened`)
