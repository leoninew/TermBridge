from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from termbridge.api import create_app
from termbridge.di import get_workspace_browser_service
from termbridge.exceptions import WorkspacePathNotDirectoryError, WorkspacePathNotFoundError
from termbridge.models import WorkspaceRoot, WorkspaceRootsResponse, WorkspaceTreeNode, WorkspaceTreeResponse
from termbridge.services import WorkspaceBrowserService
from termbridge.settings import Settings


def test_workspace_browser_lists_direct_child_directories(tmp_path: Path) -> None:
    (tmp_path / "b-dir").mkdir()
    (tmp_path / "a-dir").mkdir()
    (tmp_path / "file.txt").write_text("ignored", encoding="utf-8")
    service = WorkspaceBrowserService()

    response = service.list_children(tmp_path)

    assert [child.name for child in response.children] == ["a-dir", "b-dir"]
    assert all(child.type == "directory" for child in response.children)


def test_workspace_browser_marks_directories_with_children(tmp_path: Path) -> None:
    parent = tmp_path / "parent"
    empty = tmp_path / "empty"
    parent.mkdir()
    empty.mkdir()
    (parent / "child").mkdir()
    service = WorkspaceBrowserService()

    response = service.list_children(tmp_path)

    by_name = {child.name: child for child in response.children}
    assert by_name["parent"].has_children is True
    assert by_name["empty"].has_children is False


def test_workspace_browser_hides_dot_directories_by_default(tmp_path: Path) -> None:
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "visible").mkdir()
    service = WorkspaceBrowserService()

    response = service.list_children(tmp_path)

    assert [child.name for child in response.children] == ["visible"]


def test_workspace_browser_can_include_hidden_directories(tmp_path: Path) -> None:
    (tmp_path / ".hidden").mkdir()
    (tmp_path / "visible").mkdir()
    service = WorkspaceBrowserService()

    response = service.list_children(tmp_path, show_hidden=True)

    assert [child.name for child in response.children] == [".hidden", "visible"]


def test_workspace_browser_rejects_missing_path(tmp_path: Path) -> None:
    service = WorkspaceBrowserService()

    with pytest.raises(WorkspacePathNotFoundError):
        service.list_children(tmp_path / "missing")


def test_workspace_browser_rejects_file_path(tmp_path: Path) -> None:
    file_path = tmp_path / "file.txt"
    file_path.write_text("not a directory", encoding="utf-8")
    service = WorkspaceBrowserService()

    with pytest.raises(WorkspacePathNotDirectoryError):
        service.list_children(file_path)


class FakeWorkspaceBrowserService:
    def list_roots(self) -> WorkspaceRootsResponse:
        return WorkspaceRootsResponse(roots=[WorkspaceRoot(path="D:\\", name="D:")])

    def list_children(self, path: Path, *, show_hidden: bool = False) -> WorkspaceTreeResponse:
        if path.name == "missing":
            raise WorkspacePathNotFoundError(path)
        if path.name == "file.txt":
            raise WorkspacePathNotDirectoryError(path)
        children = [WorkspaceTreeNode(path=str(path / "child"), name="child", has_children=False)]
        if show_hidden:
            children.insert(0, WorkspaceTreeNode(path=str(path / ".hidden"), name=".hidden", has_children=False))
        return WorkspaceTreeResponse(
            path=str(path),
            name=path.name,
            children=children,
        )


def make_client() -> TestClient:
    app = create_app(Settings())
    app.dependency_overrides[get_workspace_browser_service] = lambda: FakeWorkspaceBrowserService()
    return TestClient(app)


def test_workspace_roots_api() -> None:
    client = make_client()

    response = client.get("/api/workspaces/roots")

    assert response.status_code == 200
    assert response.json() == {"roots": [{"path": "D:\\", "name": "D:", "type": "drive"}]}


def test_workspace_tree_api() -> None:
    client = make_client()

    response = client.get("/api/workspaces/tree", params={"path": "D:/SourceCodes"})

    assert response.status_code == 200
    assert response.json()["children"] == [
        {"path": str(Path("D:/SourceCodes") / "child"), "name": "child", "type": "directory", "has_children": False}
    ]


def test_workspace_tree_api_accepts_show_hidden_parameter() -> None:
    client = make_client()

    response = client.get("/api/workspaces/tree", params={"path": "D:/SourceCodes", "show_hidden": "true"})

    assert response.status_code == 200
    assert response.json()["children"][0]["name"] == ".hidden"


def test_workspace_tree_api_returns_404_for_missing_path() -> None:
    client = make_client()

    response = client.get("/api/workspaces/tree", params={"path": "D:/missing"})

    assert response.status_code == 404


def test_workspace_tree_api_returns_400_for_file_path() -> None:
    client = make_client()

    response = client.get("/api/workspaces/tree", params={"path": "D:/file.txt"})

    assert response.status_code == 400
