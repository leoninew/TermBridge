import type { Session, SessionEnvironment, SessionWorkspace } from './types/sessions'

export function workspaceDisplayLabels(
  workspaces: Pick<SessionWorkspace, 'id' | 'path'>[],
): Map<string, string> {
  const partsById = new Map(
    workspaces.map((workspace) => [workspace.id, pathParts(workspace.path)]),
  )
  const labelDepthById = new Map(workspaces.map((workspace) => [workspace.id, 1]))

  for (let changed = true; changed; ) {
    changed = false
    const idsByLabel = new Map<string, string[]>()
    for (const workspace of workspaces) {
      const parts = partsById.get(workspace.id) || []
      const depth = labelDepthById.get(workspace.id) || 1
      const label = labelFromParts(parts, depth)
      idsByLabel.set(label, [...(idsByLabel.get(label) || []), workspace.id])
    }

    for (const ids of idsByLabel.values()) {
      if (ids.length < 2) {
        continue
      }
      for (const id of ids) {
        const parts = partsById.get(id) || []
        const depth = labelDepthById.get(id) || 1
        if (depth < parts.length) {
          labelDepthById.set(id, depth + 1)
          changed = true
        }
      }
    }
  }

  return new Map(
    workspaces.map((workspace) => {
      const parts = partsById.get(workspace.id) || []
      const depth = labelDepthById.get(workspace.id) || 1
      return [workspace.id, labelFromParts(parts, depth)]
    }),
  )
}

export function workspaceDisplayLabelsById(
  environments: Pick<SessionEnvironment, 'workspaces'>[],
): Map<string, string> {
  const labels = new Map<string, string>()
  for (const environment of environments) {
    for (const [workspaceId, label] of workspaceDisplayLabels(environment.workspaces)) {
      labels.set(workspaceId, label)
    }
  }
  return labels
}

export function sessionContextLabel(
  session: Session,
  workspaceLabels: ReadonlyMap<string, string>,
): string {
  const workspaceLabel = workspaceLabels.get(session.workspace_id)
  return workspaceLabel ? `${workspaceLabel} · ${session.name}` : session.name
}

function pathParts(path: string): string[] {
  return path.replaceAll('\\', '/').split('/').filter(Boolean)
}

function labelFromParts(parts: string[], depth: number): string {
  if (parts.length === 0) {
    return ''
  }
  return parts.slice(Math.max(0, parts.length - depth)).join('/')
}
