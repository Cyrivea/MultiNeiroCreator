import request from '@/utils/request'

export type LyricsGenerateStatus = 'succeeded' | 'failed' | 'model_unavailable'

export interface LyricsGenerateResponse {
  capability_id: 'lyrics.generate'
  status: LyricsGenerateStatus
  result: {
    format: 'markdown'
    content: string
  } | null
  error: string | null
}

export interface LyricsGenerateParams {
  theme: string
  style: string
  mood: string
  language: string
}

export async function runLyricsCapability(projectId: number | null, inputs: LyricsGenerateParams) {
  return request.post<unknown, LyricsGenerateResponse>('/capabilities/run', {
    capability_id: 'lyrics.generate',
    project_id: projectId,
    inputs,
  })
}
