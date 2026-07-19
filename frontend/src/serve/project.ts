import request from '@/utils/request'

export interface ProjectPayload {
  id?: number
  name: string
  project_path: string
  save_mode: string
  created_at: string
  updated_at: string
  last_opened_at?: string
}

export interface AutoSavePayload {
  name?: string
  project_path?: string | null
  save_mode: string
}

export const createProject = (name?: string) =>
  request.post<any, { project: ProjectPayload }>('/projects', { name })

export const getRecentProjects = (limit = 8) =>
  request.get<any, { items: ProjectPayload[] }>(`/projects/recent?limit=${limit}`)

export const ensureAutoSaveProject = (data: AutoSavePayload) =>
  request.post<any, { project: ProjectPayload }>('/projects/auto-save/ensure', data)

export const createAutoBackup = (data: AutoSavePayload) =>
  request.post<any, { project: ProjectPayload; backup_file: string; backup_created_at: string }>('/projects/auto-save/backup', data)
