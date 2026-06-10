# 前端字号一致性实践

本文记录本项目前端字号使用约定，避免后续样式调整中出现多套标题字号、多套正文字号，或非标题文本误用标题字号。

## 核心原则

前端普通 UI 文本只保留两档字号：

- 标题类：`text-lg font-semibold`
- 非标题类：`text-sm`，不加粗

不要为了局部视觉微调继续引入 `text-xs`、`text-base`、`text-xl`、`text-2xl` 或 `text-[...]` 等额外字号层级。

非标题文本一律不得加粗。按钮、表单 label、badge、dropdown/menu item、状态文本等都属于非标题，不使用 `font-medium`、`font-semibold`、`font-bold` 或其他加粗类。创建会话、快捷方式这类卡片中的主名称/标题区域视为卡片标题，可使用 `text-sm font-semibold`。

## 标题类

标题类统一使用：

```html
class="text-lg font-semibold ..."
```

卡片内主名称/标题区域允许使用较小字号标题：

```html
class="text-sm font-semibold ..."
```

适用范围：

- 应用标题
- 页面标题
- 面板标题
- 卡片/区域标题
- 弹窗标题
- 分组标题

示例：

```vue
<h2 class="text-lg font-semibold text-slate-950">
  {{ title }}
</h2>
```

如果某个文本语义上是标题，即使它位于较小区域内，也优先归入标题类，而不是临时使用 `text-base` 或裸 `font-semibold`。

## 非标题类

非标题类统一使用：

```html
class="text-sm ..."
```

适用范围：

- 描述文本
- 按钮文本
- 表单 label
- input / select / textarea
- 列表项正文
- 状态文本
- 错误提示
- badge
- dropdown/menu item
- 空状态文本
- 辅助说明文本

示例：

```vue
<p class="text-sm text-slate-500">
  {{ description }}
</p>
```

```vue
<button class="rounded-xl px-3 py-2 text-sm text-white">
  {{ label }}
</button>
```

## 继承与兜底

根级页面容器应提供 `text-sm` 兜底，避免没有显式字号的普通文本回退到浏览器默认 16px：

```vue
<main class="... text-sm text-slate-900">
```

但不要只依赖根级继承。对于容易漏掉的普通文本，尤其是空状态、loading、error、menu item，建议仍显式写 `text-sm`。

弹窗、dropdown、toast 等 Portal/Teleport 内容可能挂到 `body` 下，不能保证继承页面根容器字号。其内容容器也应补 `text-sm` 兜底：

```vue
<DialogContent class="... text-sm ...">
```

标题自身使用 `text-lg`，会覆盖容器的 `text-sm`。

## 不推荐做法

不要新增局部字号层级，也不要给非标题文本加粗：

```vue
<!-- 不推荐：应用标题单独放大 -->
<h1 class="text-xl font-semibold">...</h1>

<!-- 不推荐：区域标题临时用 text-base -->
<div class="text-base font-semibold">...</div>

<!-- 不推荐：辅助文本继续缩成 text-xs -->
<p class="text-xs text-slate-500">...</p>

<!-- 不推荐：裸 font-semibold，实际字号依赖默认或父级 -->
<h3 class="font-semibold text-slate-950">...</h3>

<!-- 不推荐：非标题按钮加粗 -->
<button class="text-sm font-medium">...</button>

<!-- 不推荐：非标题 label 加粗 -->
<label class="text-sm font-medium">...</label>

<!-- 不推荐：badge / 状态文本加粗 -->
<span class="text-sm font-semibold">...</span>
```

推荐改成：

```vue
<!-- 标题 -->
<h1 class="text-lg font-semibold text-slate-950">...</h1>

<!-- 非标题 -->
<p class="text-sm text-slate-500">...</p>
```

## 修改检查清单

调整前端 UI 字号时，至少检查：

- [ ] 页面、面板、弹窗标题是否统一为 `text-lg font-semibold`。
- [ ] 创建会话、快捷方式等卡片主名称/标题区域是否可识别为 `text-sm font-semibold`。
- [ ] 非标题文本是否统一为 `text-sm`。
- [ ] 非标题文本是否没有 `font-medium`、`font-semibold`、`font-bold` 或其他加粗类。
- [ ] 是否误引入 `text-xs`、`text-base`、`text-xl`、`text-2xl` 或 `text-[...]`。
- [ ] 空状态、loading、error 文本是否有 `text-sm`。
- [ ] Portal/Teleport 内容容器是否有 `text-sm` 兜底。
- [ ] 是否有裸 `font-semibold` 但未明确标题字号的标题元素。

可用搜索检查：

```bash
rg "text-(xs|base|xl|2xl|\[[^\]]+\])|font-(medium|semibold|bold|extrabold)" frontend/src
```

也可以重点搜索没有显式字号的状态文本、弹窗按钮、菜单项等。

## 当前约定背景

本约定来自 2026-06-09 的前端字号收敛：

- 标题统一到 `text-lg`。
- 非标题统一到 `text-sm`。
- “暂无会话，先创建一个。”这类空状态文本从隐式默认 16px 修正为 `text-sm`。
- 未抽取额外语义类，保持 Tailwind 原子类的机械收敛方式。
