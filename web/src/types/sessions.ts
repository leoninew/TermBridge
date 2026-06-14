export type SessionStatus = 'starting' | 'running' | 'disconnected' | 'stopped' | 'failed'
export type SessionPersistence = 'none' | 'tmux'
export type TtydMode = 'auto' | 'explicit'
export type ShortcutHost = 'windows_cygwin' | 'windows_wsl' | 'linux'
export type EnvironmentReadiness = 'not_ready' | 'ready'

export interface Session {
  id: string
  workspace_id: string
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

export interface SessionWorkspace {
  id: string
  host: ShortcutHost
  name: string
  path: string
  status: SessionStatus
  entries: Session[]
}

export interface SessionEnvironment {
  host: ShortcutHost
  label: string
  workspaces: SessionWorkspace[]
}

export interface SessionTreeResponse {
  environments: SessionEnvironment[]
}

export interface ReorderWorkspacesPayload {
  workspace_ids: string[]
}

export interface ReorderSessionsPayload {
  session_ids: string[]
}

export interface CloseAllSessionsResponse {
  stopped_count: number
  tmux_session_count: number
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

export interface EnvironmentSummary {
  host: ShortcutHost
  label: string
  readiness: EnvironmentReadiness
  available_on_host: boolean
  checked_at?: string | null
  last_error?: string | null
}

export interface EnvironmentListResponse {
  environments: EnvironmentSummary[]
}

export interface WindowsCygwinSettings {
  readiness: EnvironmentReadiness
  bash_path?: string | null
  tmux_path?: string | null
  checked_at?: string | null
  last_error?: string | null
}

export interface WindowsWslSettings {
  readiness: EnvironmentReadiness
  wsl_path?: string | null
  wsl_version?: string | null
  default_distro?: string | null
  automount_root?: string | null
  tmux_path?: string | null
  tmux_version?: string | null
  shell_path?: string | null
  checked_at?: string | null
  last_error?: string | null
}

export interface LinuxSettings {
  readiness: EnvironmentReadiness
  shell_path?: string | null
  tmux_path?: string | null
  checked_at?: string | null
  last_error?: string | null
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
