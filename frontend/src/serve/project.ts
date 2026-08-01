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

export const createProject = (name?: string, projectPath?: string) =>
  request.post<any, { project: ProjectPayload }>('/projects', { name, project_path: projectPath })

export const getRecentProjects = (limit = 8) =>
  request.get<any, { items: ProjectPayload[] }>(`/projects/recent?limit=${limit}`)
