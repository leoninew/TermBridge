from __future__ import annotations

from urllib.parse import parse_qsl, urlencode

TTYD_DEFAULT_THEME = "dark"

TTYD_THEMES = {
    "dark": (
        '{"background":"#020617","foreground":"#e2e8f0","cursor":"#e2e8f0",'
        '"selectionBackground":"#1e3a8a","black":"#0f172a","red":"#f87171",'
        '"green":"#34d399","yellow":"#facc15","blue":"#60a5fa","magenta":"#c084fc",'
        '"cyan":"#22d3ee","white":"#e2e8f0","brightBlack":"#475569",'
        '"brightRed":"#fca5a5","brightGreen":"#6ee7b7","brightYellow":"#fde047",'
        '"brightBlue":"#93c5fd","brightMagenta":"#d8b4fe","brightCyan":"#67e8f9",'
        '"brightWhite":"#f8fafc"}'
    ),
    "light": (
        '{"background":"#f8fafc","foreground":"#0f172a","cursor":"#0f172a",'
        '"selectionBackground":"#bfdbfe","black":"#0f172a","red":"#dc2626",'
        '"green":"#059669","yellow":"#ca8a04","blue":"#2563eb","magenta":"#9333ea",'
        '"cyan":"#0891b2","white":"#e2e8f0","brightBlack":"#64748b",'
        '"brightRed":"#ef4444","brightGreen":"#10b981","brightYellow":"#eab308",'
        '"brightBlue":"#3b82f6","brightMagenta":"#a855f7","brightCyan":"#06b6d4",'
        '"brightWhite":"#ffffff"}'
    ),
}

TTYD_BASE_CLIENT_OPTIONS = {
    "fontSize": "13",
    "fontFamily": "Cascadia Code,Consolas,Liberation Mono,monospace",
    "cursorBlink": "true",
}


def ttyd_client_options(theme: str = TTYD_DEFAULT_THEME) -> dict[str, str]:
    return {"theme": TTYD_THEMES.get(theme, TTYD_THEMES[TTYD_DEFAULT_THEME]), **TTYD_BASE_CLIENT_OPTIONS}


def normalize_ttyd_client_query(query: str) -> str:
    if not query:
        return ""

    params = [
        (key, TTYD_THEMES.get(value, value) if key == "theme" else value)
        for key, value in parse_qsl(query, keep_blank_values=True)
    ]
    return urlencode(params)
