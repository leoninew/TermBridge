export type SessionStatus = 'starting' | 'running' | 'stopped' | 'failed'
export type SessionPersistence = 'none' | 'tmux'
export type TtydMode = 'auto' | 'explicit'
export type ShortcutHost = 'windows_cygwin' | 'windows_wsl' | 'linux'

export interface Session {
  id: string
  name: string
  workspace: string
  runtime: string
  status: SessionStatus
  port: number
  url: string
  shortcut_id?: string | null
  shortcut_name?: string | null
  host?: ShortcutHost | null
  session_persistence: SessionPersistence
  tmux_session_name?: string | null
  created_at: string
  updated_at: string
}

export interface CreateSessionPayload {
  name: string
  workspace: string
  shortcut_id: string
}

export interface HealthResponse {
  status?: string
  [key: string]: unknown
}

export interface WorkspaceRoot {
  path: string
  name: string
  type: 'drive'
}

export interface WorkspaceTreeNode {
  path: string
  name: string
  type: 'directory'
  has_children: boolean
}

export interface WorkspaceRootsResponse {
  roots: WorkspaceRoot[]
}

export interface WorkspaceTreeResponse {
  path: string
  name: string
  children: WorkspaceTreeNode[]
}

export interface RuntimeCheckResponse {
  available: boolean
  path?: string | null
  version?: string | null
  reason?: string | null
}

export interface Shortcut {
  id: string
  name: string
  command: string
  host: ShortcutHost
  description?: string | null
}

export interface ShortcutListResponse {
  shortcuts: Shortcut[]
}

export interface CreateShortcutPayload {
  name: string
  command: string
  host: ShortcutHost
  description?: string | null
}

export interface UpdateShortcutPayload {
  name?: string
  command?: string
  host?: ShortcutHost
  description?: string | null
}

export interface TerminalSettings {
  ttyd_mode: TtydMode
  ttyd_path?: string | null
}

export interface WindowsCygwinSettings {
  bash_path?: string | null
  tmux_path?: string | null
}

export interface WindowsCygwinCheckResponse {
  host: RuntimeCheckResponse
  bash: RuntimeCheckResponse
  tmux?: RuntimeCheckResponse | null
}

export interface WindowsWslCheckResponse {
  host: RuntimeCheckResponse
  wsl: RuntimeCheckResponse
  tmux?: RuntimeCheckResponse | null
}

export interface LinuxCheckResponse {
  host: RuntimeCheckResponse
  shell?: RuntimeCheckResponse | null
  tmux?: RuntimeCheckResponse | null
}

export interface TmuxAvailabilityResponse {
  available: boolean
  path?: string | null
  version?: string | null
  reason?: string | null
}

export interface TmuxAvailabilityPayload {
  cygwin_bash_path: string
}
