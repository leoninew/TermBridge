import { i18n } from '../i18n'
import type {
  CloseAllSessionsResponse,
  CreateSessionPayload,
  CreateShortcutPayload,
  EnvironmentListResponse,
  HealthResponse,
  LinuxCheckResponse,
  ReorderSessionsPayload,
  ReorderShortcutsPayload,
  ReorderWorkspacesPayload,
  RuntimeCheckResponse,
  Session,
  SessionTreeResponse,
  Shortcut,
  ShortcutListResponse,
  TerminalSettings,
  UpdateShortcutPayload,
  WindowsCygwinCheckResponse,
  WindowsCygwinSettings,
  WindowsWslCheckResponse,
  WindowsWslSettings,
  WorkspaceRootsResponse,
  WorkspaceTreeResponse,
} from '../types/sessions'

type ApiErrorResponse = {
  code: string
  error: string
}

export class ApiError extends Error {
  constructor(
    message: string,
    readonly code: string,
    readonly status: number,
  ) {
    super(message)
    this.name = 'ApiError'
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
    ...init,
  })

  if (!response.ok) {
    throw await readError(response)
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

async function readError(response: Response): Promise<ApiError> {
  try {
    const data = (await response.json()) as ApiErrorResponse
    if (data.code && data.error) {
      return new ApiError(data.error, data.code, response.status)
    }
  } catch {
    // Fall through to the generic request failure below.
  }
  return new ApiError(
    i18n.global.t('api.requestFailed', { status: response.status }),
    'request_failed',
    response.status,
  )
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}

export function listSessions(): Promise<Session[]> {
  return request<Session[]>('/api/sessions')
}

export function listSessionTree(options?: { refresh?: boolean }): Promise<SessionTreeResponse> {
  const query = options?.refresh === false ? '?refresh=false' : ''
  return request<SessionTreeResponse>(`/api/session-tree${query}`)
}

export function reorderEnvironmentWorkspaces(
  host: string,
  payload: ReorderWorkspacesPayload,
): Promise<SessionTreeResponse> {
  return request<SessionTreeResponse>(
    `/api/session-tree/environments/${encodeURIComponent(host)}/workspaces/order`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
  )
}

export function reorderWorkspaceSessions(
  workspaceId: string,
  payload: ReorderSessionsPayload,
): Promise<SessionTreeResponse> {
  return request<SessionTreeResponse>(
    `/api/session-workspaces/${encodeURIComponent(workspaceId)}/sessions/order`,
    {
      method: 'PUT',
      body: JSON.stringify(payload),
    },
  )
}

export function createSession(payload: CreateSessionPayload): Promise<Session> {
  return request<Session>('/api/sessions', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function getSession(id: string): Promise<Session> {
  return request<Session>(`/api/sessions/${encodeURIComponent(id)}`)
}

export function startSession(id: string): Promise<Session> {
  return request<Session>(`/api/sessions/${encodeURIComponent(id)}/start`, {
    method: 'POST',
  })
}

export function stopSession(id: string): Promise<Session> {
  return request<Session>(`/api/sessions/${encodeURIComponent(id)}/stop`, {
    method: 'POST',
  })
}

export function closeAllSessions(): Promise<CloseAllSessionsResponse> {
  return request<CloseAllSessionsResponse>('/api/sessions/close-all', {
    method: 'POST',
  })
}

export function deleteSession(id: string): Promise<void> {
  return request<void>(`/api/sessions/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })
}

export function deleteSessionWorkspace(id: string): Promise<void> {
  return request<void>(`/api/session-workspaces/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })
}

export function getWorkspaceRoots(): Promise<WorkspaceRootsResponse> {
  return request<WorkspaceRootsResponse>('/api/workspaces/roots')
}

export function getWorkspaceTree(path: string): Promise<WorkspaceTreeResponse> {
  return request<WorkspaceTreeResponse>(`/api/workspaces/tree?path=${encodeURIComponent(path)}`)
}

export function listShortcuts(): Promise<ShortcutListResponse> {
  return request<ShortcutListResponse>('/api/shortcuts')
}

export function createShortcut(payload: CreateShortcutPayload): Promise<Shortcut> {
  return request<Shortcut>('/api/shortcuts', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function updateShortcut(id: string, payload: UpdateShortcutPayload): Promise<Shortcut> {
  return request<Shortcut>(`/api/shortcuts/${encodeURIComponent(id)}`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function reorderShortcuts(
  host: string,
  payload: ReorderShortcutsPayload,
): Promise<ShortcutListResponse> {
  return request<ShortcutListResponse>(`/api/shortcuts/environments/${encodeURIComponent(host)}/order`, {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function deleteShortcut(id: string): Promise<void> {
  return request<void>(`/api/shortcuts/${encodeURIComponent(id)}`, {
    method: 'DELETE',
  })
}

export function getTerminalSettings(): Promise<TerminalSettings> {
  return request<TerminalSettings>('/api/terminal-settings')
}

export function updateTerminalSettings(payload: TerminalSettings): Promise<TerminalSettings> {
  return request<TerminalSettings>('/api/terminal-settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function checkTtyd(path?: string): Promise<RuntimeCheckResponse> {
  return request<RuntimeCheckResponse>('/api/environment/ttyd/check', {
    method: 'POST',
    body: JSON.stringify({ path: path || null }),
  })
}

export function listEnvironments(): Promise<EnvironmentListResponse> {
  return request<EnvironmentListResponse>('/api/environments')
}

export function getWindowsCygwinSettings(): Promise<WindowsCygwinSettings> {
  return request<WindowsCygwinSettings>('/api/environment/windows-cygwin/settings')
}

export function updateWindowsCygwinSettings(
  payload: WindowsCygwinSettings,
): Promise<WindowsCygwinSettings> {
  return request<WindowsCygwinSettings>('/api/environment/windows-cygwin/settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function checkWindowsCygwin(bashPath?: string): Promise<WindowsCygwinCheckResponse> {
  return request<WindowsCygwinCheckResponse>('/api/environment/windows-cygwin/check', {
    method: 'POST',
    body: JSON.stringify({ bash_path: bashPath || null }),
  })
}

export function getWindowsWslSettings(): Promise<WindowsWslSettings> {
  return request<WindowsWslSettings>('/api/environment/windows-wsl/settings')
}

export function updateWindowsWslSettings(payload: WindowsWslSettings): Promise<WindowsWslSettings> {
  return request<WindowsWslSettings>('/api/environment/windows-wsl/settings', {
    method: 'PUT',
    body: JSON.stringify(payload),
  })
}

export function checkWindowsWsl(): Promise<WindowsWslCheckResponse> {
  return request<WindowsWslCheckResponse>('/api/environment/windows-wsl/check', { method: 'POST' })
}

export function checkLinux(): Promise<LinuxCheckResponse> {
  return request<LinuxCheckResponse>('/api/environment/linux/check', { method: 'POST' })
}
