import { i18n } from '../i18n'
import type {
  CreateSessionPayload,
  CreateShortcutPayload,
  HealthResponse,
  LinuxCheckResponse,
  RuntimeCheckResponse,
  Session,
  Shortcut,
  ShortcutListResponse,
  TerminalSettings,
  TmuxAvailabilityPayload,
  TmuxAvailabilityResponse,
  UpdateShortcutPayload,
  WindowsCygwinCheckResponse,
  WindowsCygwinSettings,
  WindowsWslCheckResponse,
  WorkspaceRootsResponse,
  WorkspaceTreeResponse,
} from '../types/sessions'

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(path, {
    headers: {
      'Content-Type': 'application/json',
      ...init?.headers,
    },
    ...init,
  })

  if (!response.ok) {
    const detail = await readError(response)
    throw new Error(detail || i18n.global.t('api.requestFailed', { status: response.status }))
  }

  if (response.status === 204) {
    return undefined as T
  }

  return response.json() as Promise<T>
}

async function readError(response: Response): Promise<string> {
  try {
    const data = (await response.json()) as { detail?: string; message?: string }
    return data.detail || data.message || response.statusText
  } catch {
    return response.statusText
  }
}

export function getHealth(): Promise<HealthResponse> {
  return request<HealthResponse>('/health')
}

export function listSessions(): Promise<Session[]> {
  return request<Session[]>('/api/sessions')
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

export function restartSession(id: string): Promise<Session> {
  return request<Session>(`/api/sessions/${encodeURIComponent(id)}/restart`, {
    method: 'POST',
  })
}

export function deleteSession(id: string): Promise<void> {
  return request<void>(`/api/sessions/${encodeURIComponent(id)}`, {
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
  const query = path ? `?path=${encodeURIComponent(path)}` : ''
  return request<RuntimeCheckResponse>(`/api/environment/ttyd/check${query}`)
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
  const query = bashPath ? `?bash_path=${encodeURIComponent(bashPath)}` : ''
  return request<WindowsCygwinCheckResponse>(`/api/environment/windows-cygwin/check${query}`)
}

export function checkTmux(payload: TmuxAvailabilityPayload): Promise<TmuxAvailabilityResponse> {
  return request<TmuxAvailabilityResponse>('/api/terminals/tmux/check', {
    method: 'POST',
    body: JSON.stringify(payload),
  })
}

export function checkWindowsWsl(): Promise<WindowsWslCheckResponse> {
  return request<WindowsWslCheckResponse>('/api/environment/windows-wsl/check')
}

export function checkLinux(): Promise<LinuxCheckResponse> {
  return request<LinuxCheckResponse>('/api/environment/linux/check')
}
