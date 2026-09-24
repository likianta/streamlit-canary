# AGENTS.md

> 对 AI agent 的项目指引. 每当 agent 进入此仓库工作时, 请先阅读本文档.

## 1. 项目概况

**Streamlit Canary** (`streamlit-canary`) 是对 Streamlit 的二次开发, 扩展了原版的组件库, 并实现了一套基于事件驱动的运行时. 开发者用纯 Python 写组件树, 运行时负责渲染 HTML, 路由事件, 推送 delta patch, 前端局部更新 DOM, 无需页面刷新.

### 核心理念

传统 Streamlit 采用 "rerun" 模型 -- 每次交互都重新执行整个脚本. Streamlit Canary 的事件驱动运行时 (v3) 采用 **no-rerun** 模型:

1. 应用函数只运行一次, 构建组件树
2. 用户交互 (点击, 选择) 通过 WebSocket 发送事件到后端
3. Runtime 将事件路由到对应组件的 Signal
4. 属性变更触发 delta patch, 通过 WebSocket 推送到前端
5. 前端局部更新 DOM, 无需页面刷新

## 2. 目录结构

```
streamlit-canary/
├── streamlit_canary/         # 主包
│   ├── kernel/               # 事件驱动内核 (无 Streamlit 依赖)
│   │   ├── property.py       # 响应式属性
│   │   ├── signal.py         # 事件信号
│   │   ├── special_value.py  # sc._self / sc._value 的特殊标记
│   │   └── state.py          # 状态容器
│   ├── components_v3/        # v3 事件驱动组件 (纯 Python, 无 Streamlit 依赖)
│   │   ├── base.py           # Component 基类: 组件树, 上下文栈, 注册到 runtime
│   │   ├── _shared.py        # 共享私有基类 + 助手 (非 public API)
│   │   ├── texts.py          # 文本元素 (Streamlit: Text elements)
│   │   ├── data.py           # 数据元素 (Data elements)
│   │   ├── charts.py         # 图表元素 (Chart elements)
│   │   ├── buttons.py        # 按钮类 (Input widgets 的按钮部分)
│   │   ├── inputs.py         # 取值类 (Input widgets 的输入部分)
│   │   ├── layouts.py        # 布局与容器 (Layouts and containers)
│   │   ├── status.py         # 状态元素 (Status elements)
│   │   └── trees/                        # 自研文件夹浏览器 (TreeSelect 家族)
│   │       ├── __init__.py               # 导出 PathInput / Recent / TreeSelect 家族
│   │       ├── _shared.py                # 导航, 选项, 路径的私有助手
│   │       ├── recent.py                 # 最近路径下拉
│   │       ├── tree_select.py            # TreeSelect / TreeSelectWithInput
│   │       └── tree_select_dual_pane.py  # 双栏 TreeSelect
│   ├── runtime/              # 事件驱动运行时
│   │   ├── runtime.py        # Runtime: 持久组件树 + 事件路由 + delta 广播
│   │   ├── render.py         # 组件树 → HTML
│   │   ├── server.py         # Starlette 应用 + WebSocket 端点
│   │   └── static/           # 前端资源
│   ├── components/           # v1 组件 (基于 Streamlit)
│   ├── components_v2/        # v2 组件 (过渡版本)
│   ├── session.py            # v1/v2 session state 管理
│   └── runner.py             # 传统 Streamlit 子进程启动器 (legacy)
├── examples/
│   ├── click_counter.py      # 计数器示例 (最小 v3 演示用例)
│   └── ...
├── test/                               # 测试与演示 (你可以在本目录下根据需要创建新的测试脚本)
│   ├── event_driven_system/            # v3 事件驱动测试
│   │   ├── components_v3_demo.py       # 纯 Python 组件树 / 信号演示
│   │   └── ...
│   ├── pixel_fidelity/                 # UI 像素级对齐的试验脚本
│   ├── rewrite_third_party_projects/   # 基于 v3 组件重写第三方项目
│   │   ├── asa_gui_copy/
│   │   ├── pdf_watermaker_copy/
│   │   ├── pyproject_manager_copy/
│   │   └── ...
│   └── ...
├── references/               # 参考资源
│   ├── asa_gui/              # 原版基于 Streamlit 的演示应用, 运行在 localhost:2204
│   ├── pdf_watermaker/       # 原版基于 Streamlit 的演示应用, 运行在 localhost:2210
│   ├── pyproject_manager/    # 原版基于 Streamlit 的演示应用, 运行在 localhost:2206
│   ├── streamlit/            # Streamlit (v1.63.0) 源码
│   └── ...                   # 截图, 参考图等
├── .trae/documents/          # 设计/路线图文档与像素对比差异说明
├── pyproject.toml            # 项目配置
├── readme.md                 # 简要说明
└── changelog.md              # 变更记录
```

## 3. 开发环境

### 常用命令

```bash
# 同步依赖
uv sync

# 运行 v3 测试应用
python test/rewrite_third_party_projects/pyproject_manager_copy/app.py  # :2207

# 运行最小 v3 demo (计数器, 参考用法见其 docstring)
python test/event_driven_system/demo_click_counter.py  # :2201

# 运行原版 (用于对比)
# 原版 pyproject-manager 运行在 :2206

# 静态检查
ruff check streamlit_canary/
ruff format streamlit_canary/
ty check streamlit_canary/

# 运行内核测试
python test/property_test.py
python test/signal_test.py
python test/event_driven_system/components_v3_demo.py
```

### 端口说明

我们在本地 (localhost) 提供了 :2200 到 :2229 共 30 个端口专为本项目使用. 目前定义如下:

```yaml
2200: 默认的 streamlit 应用端口, 常见于 sc.run 函数的默认值, 以及基于 streamlit 的应用的临时测试.
2201: 默认的 streamlit canary (v3) 应用端口. 常见于基于 streamlit canary v3 的应用的临时测试.
2202: 高保真对比测试端口 (streamlit), 见 ./test/pixel_fidelity/ui_scene_st.py
2203: 高保真对比测试端口 (streamlit-canary), 见 ./test/pixel_fidelity/ui_scene_sc.py
2204: ASA GUI 原版应用.
2205: ASA GUI 副本应用. 也就是我们正在用 v3 组件重写并测试的应用.
2206: PyProject Manager 原版应用.
2207: PyProject Manager 副本应用. 也就是我们正在用 v3 组件重写并测试的应用.
2208: 未使用, 待定义.
2209: 未使用, 待定义.
2210: PDF Watermaker 原版应用.
2211: PDF Watermaker 副本应用.
2212...2229: 暂未定义, 未来会根据需要添加.
```

### Playwright 使用说明

本项目已经安装了 playwright 依赖, 并且下载了 chromium 浏览器 (位于 `C:\Users\Likianta\AppData\Local\ms-playwright\chromium_headless_shell-1243`).

因为 chromium 是安装在全局的, 所以不需要配置额外的 playwright 环境变量. 直接在脚本中调用即可:

```python
from playwright.sync_api import sync_playwright

with sync_playwright() as p:
    browser = p.chromium.launch(headless=True)
    page = browser.new_page()
    page.goto('http://localhost:2201')
    # testing...
    browser.close()
```

## 4. 伪代码驱动的 UI 验证方法

在与 Agent 交流 UI 交互和视觉要求时, **纯文字描述往往不够精确**. 推荐使用 **伪代码 (pseudo-code)** 来描述交互操作和断言.

### 为什么用伪代码

- 文字描述容易遗漏细节 (如 "hover 时背景应该是灰色" -- 哪个元素的灰色? 和谁对齐?)
- 伪代码可以精确表达:
  - **操作序列**: 先做什么, 再做什么
  - **目标元素**: 通过属性或层级定位
  - **断言条件**: 具体的 CSS 属性值, 几何关系
- Agent 可以直接把伪代码翻译为浏览器自动化行为

### 伪代码示例

伪代码不需要可执行, 但需要描述测试意图和可被自动化实现的操作步骤:

```
# 1. 打开应用, 定位元素
sc_app = open_browser(localhost:2201)
sel = sc_app.find_element(project_scope_selectbox)

# 2. 静态断言 (无交互)
assert sel.container.text.alignment is left, not center

# 3. 交互 + 断言
when mouse.click(sel):
    # 展开后的面板
    children = sel.expanded_panel.children

    # 遍历检查
    for child in children:
        assert not mouse.has_enter(child)
        assert child.background_color != highlighting_background_color

    # 悬浮某个元素后的断言
    when mouse.enter(children[1]):
        assert children[0].background_color != highlighting_background_color
        assert children[1].background_color == highlighting_background_color
        assert children[2].background_color != highlighting_background_color

        # 几何断言
        assert children[1].background.horizontal_visual_margin > 0
```

### Agent 工作流

当用户提供伪代码时, Agent 应该:

1. **解析伪代码**: 识别操作序列, 目标元素, 断言条件
2. **采集数据**: 用 `browser_evaluate` 在原版 (`:2204` / `:2206`) 和副本 (`:2205` / `:2207`) 分别采集断言处的实际值
3. **对比分析**: 找出差异
4. **修复代码**: 按需改以下位置 --
   - `components_v3/<分类>.py` -- 组件定义 / 属性 (分类见 §7)
   - `runtime/render.py` -- HTML 结构
   - `runtime/static/page.css` -- 样式
   - `runtime/static/page.js` -- 前端交互 (事件回传 / delta patch)
5. **重新验证**: 重启服务 (前端资源在启动时读入, 改动后必须重启), 再次采集数据, 确认所有 assert 通过

### 4.4 像素对比测试前必读

在跑 `./test/pixel_fidelity/` 下的任何对比测试之前 (以及在据其结果判断 "这算不算 bug" 之前), 先读一遍 `.trae/documents/pixel_fidelity_caveats.md`.

该文档列出了我们**有意为之**的差异. 与 Streamlit 不一致的地方都先在这里对号入座: 不要把预期差异当成 bug 去 "修".

## 5. 工具链

- 使用 `python ...` 运行脚本 (已配置 `PYTHONPATH`,不需要 `sys.path.append`).
- 使用 `uv sync` 同步依赖, 使用 `uv` 管理 `pyproject.toml` 中的依赖.
- 使用 `ty check` 检查类型错误.
- 使用 `ruff check` 检查代码风格, 使用 `ruff format` 格式化代码.
- 每当完成修改后, 运行 `ty check`、`ruff check`、`ruff format` 确认无误.

## 6. 代码风格

- 优先使用 `<str>.format` 而不是 `f-string`.
- 代码中使用全英文注释, 不要有中文注释.
- 不需要在入口脚本的顶部添加 `sys.path.append(...)`. 因为我们已经设置好了环境变量 (`PYTHONPATH=.;src;lib;.venv/Lib/site-packages`).
- 不要在代码中添加 `from __future__ import annotations`.
- 每行代码不超过 80 字符 (见 `pyproject.toml:[tool.ruff]:line-length`).
- import 使用 force-single-line 风格 (见 `pyproject.toml:[tool.ruff.lint.isort]`).
- 字符串使用单引号 (见 `pyproject.toml:[tool.ruff.format]:quote-style`).
- 同一模块内的 class 按字母序排列 (私有基类因为要先于使用者定义, 可集中放在文件前部, 如 `components_v3/_shared.py`).
- 在代码注释 (`#` 开头的注释), `print(...)` 以及 `Exception(...)` 中使用小写字母开头的句子. 在函数注解 (docstring) 以及 triple-quoted strings 中, 使用规范的大小写格式.

## 7. 代码提交

如果涉及到文件改动, 并且产生 git 差异, 则在回复的末尾给我提供一个 commit 信息参考 (不要自己提交, 我会复制这个信息然后手动提交).

Commit 信息格式: 英文, 全小写字符, 建议在 50 字符以内, 如果改动过多导致信息过多, 可以省略不重要的内容. 参考我最近几次历史提交信息文本风格.

如果只修改了 gitignore 文件, 没有产生 git 差异, 则不需要提供 commit 信息参考.

## 8. 架构约束

- **State 和 Components 统一读写风格**: `.get()` / `.set()` / `__getitem__` / `__setitem__` / `on_change`, 降低理解负担.
- **组件属性**: 可响应字段用 `Property` (如 `Text.text`, `Selectbox.value`, `Button.type`), 静态配置用 `_` 前缀属性(如 `Code._language`, `LogPanel._source`, `Callout._kind`). 由别的字段派生的展示字段 (如 `ToggleButton.type` 跟它自己的 `value` 走) 用 `_shared._derive` 造一个**只读** `Property` (`_ReadOnlyProperty`): 能读能监听 (照常收发 patch), 但 `.set(...)` / `comp['x'] = ...` 会抛 `AttributeError` (内部更新走 `_write`), 免得被外部改成和来源不一致. 另有 `_visible_when_filled` 派生 `visible` (可写, 语义见下条).
- **v2/v3 命名空间**: v2/v3 的新元素不直接暴露在 `__init__.py`, 用 `components_v3` 作为 v3 命名空间 (如 `sc.v3.Button`).
- **`references/` 只读**: `references/` 目录 (含其中以软链接形式挂载的参考项目) 对 agent 是**只读**的, 不要修改其中的任何文件; 只可读取作为参考.
- **组件复用**: 多个组件共用的字段 / 逻辑抽到 `components_v3/_shared.py` 的私有基类 (`_HasText` / `_Labeled` / `_OptionsWidget` / `_TextVisible`) 或混入 (`_HasPlaceholder` / `_Submittable` / `_RowGestures`, 后者因为在 `_Labeled` 处已汇合而没有单一 `super()` 可链, 各自用 `_init_*` 显式调用). 组件字段在 `__init__` 中用 `_prop(default, source)` 声明, 以同时支持传入普通值或 `Property`.
- **`label_visibility` 的四个值与 `auto` 默认**: 带 label 的组件 (继承 `_Labeled` / `_OptionsWidget` 的那些) 都接受 `label_visibility`, 取值见 `components_v3/inputs.py` 的 `T.LabelVisibility`: `'auto'` (默认) | `'visible'` | `'hidden'` | `'collapsed'`. `'auto'` 在渲染期由 `runtime/render.py` 的 `_widget_label_html` 判定一次: label 有内容就等同 `'visible'`, 否则等同 `'collapsed'` (空 label 否则仍会占住标签行的 24px + 4px). 注意 `label_visibility` 是静态字段而 `label` 是可绑定的, 所以 `'auto'` 按渲染那一刻的 label 判定, 之后 label 变化不会重新判定 (要动态得先给它加 patch 通道). 新增带 label 的组件请继承 `_Labeled`, 不要自己拼 label 的 HTML -- `_widget_label_html` 是唯一的 label 渲染入口.
- **内容为空即隐藏 (`_visible_when_filled`)**: `Text` / `Title` / `Caption` / `PageTitle` (经 `_HelpText`)、`Markdown` / `Code` / `Table` / `PdfViewer` / `LogPanel` 与 `Callout` 族 (`Info` / `Error` / `Success` / `Warning`) 的 `visible` 是"内容非空"与构造参数的 **AND**: 在 `__init__` 里 `self.visible = _visible_when_filled(self.text, visible)` (或等价的 `rows` / `src` / `lines`), 内容为空 (字面为空, 见 `_is_blank`) 即隐藏, 显式 `visible=False` 也隐藏, **两者都为真才渲染**; 所以这些组件的 `visible` 参数默认都是 `True`. 想要一个"占住位置但什么都不显示"的元素 (即原版 `st.title('')` 那种空行), 就写一个**空格占位符** (`v3.Title(' ')`) -- **只有严格一个空格** (`' '`) 算内容; 其余纯空白串 (`'\t'` / `'\n'` / `'  '`) 一律算空 (见 `_is_blank`), 而且判定发生在组件**整理过输入之后** -- `Markdown` 会先 `dedent` + `strip`, 所以 `Markdown('\n')` 也算空. 空白占位在样式上也要托住: `.st-plain` 与 `.st-md[data-md=' ']` 用 `white-space: pre-wrap`, 块制的再补 `min-height: 1lh` (markdown-it 会把"只有一个空格的块"整块丢掉). `Spinner` / `Progress` 是例外 -- 它们的 `visible` 默认 `False`, 是"用时才现身"的显式开关, 不由内容决定 (所以 `_TextVisible` 基类不再强设默认值, 改由各子类声明). 隐藏只是给根元素加 `hidden`, 元素仍在 DOM 里, 后续 `text` patch 能把它带回来; 浏览器那侧靠 `[hidden] { display: none }` -- 少数自己设了 `display` 的盒子 (`.st-tabs` / `.st-grid` / `.st-grid-cell`) 会把它压过去, 因此这些必须自带一条 `[hidden] { display: none }` (多数不设 `display` 的盒子不用, 见 `33-buttons.css` 里的注释). 文本元素共用 `_HelpText`, 因此新增文本类组件继承它就自动获得这条规则.
- **`Title(horizontal_alignment=...)` 与 `PageTitle`**: `Title` 多一个静态字段 `horizontal_alignment` (`'left'` 默认 | `'center'` | `'right'`, 校验见 `texts.py` 的 `_validate_alignment`), 渲染时左对齐不加类、另两种加 `st-title--center` / `st-title--right` (`10-texts.css`). `PageTitle` 是 `Title` 的子类, 额外把网页 `<title>` 设成自己的 `text` (canary 独有): 首次绘制由 `render_page` 走一遍组件树 (`_walk_tree` / `_find_page_title`) 让**最后一个** `PageTitle` 覆盖 `set_page_config(title)` 的默认名, 之后 `text` 一变, 前端 (`50-markdown.js` 的 `scPatchText`) 就把 `document.title` 同步成**原文** (页签用纯文本 -- 标题元素才解析 markdown). 元素上多一个 `st-page-title` 类, 就是前端据此判断的标记.
- **组件按 Streamlit 分类分模块**: `components_v3/` 下按 Streamlit API reference 的分类分文件, 模块名统一用复数形式 (`data` / `status` 单复数同形) -- `texts` (Text elements) / `data` / `charts` / `buttons` + `inputs` (Input widgets 一分为二) / `layouts` (Layouts and containers) / `status`; 分类表与官方对照见 `components_v3/__init__.py` 的模块 docstring, 原始分类清单在 `references/streamlit_api_reference_catagory.html`. 组件与 Streamlit 的对应关系 (以及我们自研的部分) 以该 docstring 为准.
- **前端资源独立存放**: CSS / JS 放在 `runtime/static/` (`markdown-it.min.js` / `emoji-shortcodes.js` / `theme-*.css` / `fonts`), 用 `lk_utils.fs.load(fs.here(...), 'plain')` 在模块加载期读入; 不要在 Python 里内联大段 CSS / JS. 因此 **改动这些文件后必须重启服务**. 其中 `markdown-it.min.js` 与 `emoji-shortcodes.js` 不由 `page.js` 那个包承载, 而是各自一个 `/static/...` 路由 (`server.py`), 由页面 `<script src>` 引入 -- 为的是别把页面 HTML 撑大, 也让浏览器能跨刷新缓存它们; `emoji-shortcodes.js` 是 `test/gen_emoji_shortcodes.py` 从 Streamlit 自带的 node-emoji 数据生成的, 升级 Streamlit 后想跟进新 emoji 就重跑它.
- **样式表与脚本按组件分块**: `page.css` / `page.js` 这两个"页面级包"不再各是一个大文件, 而是分别由 `runtime/static/css/*` 与 `runtime/static/js/*` 下的分块文件按固定顺序拼成 (`render.py` 的 `_PAGE_CSS` / `_PAGE_JS` 列表就是唯一权威的顺序, 数字前缀与之一致). 拼接顺序即 CSS 层叠顺序, 所以要**按列表改**, 不要随手调整文件名或顺序; 其它文档 / 注释里提到的 "`page.css`" / "`page.js`" 都指这两个包, 按分块文件名 (如 `35-choice.css`) 或选择器名去 grep 即可.
- **组件尺寸与高度上下限**: 所有组件都接受统一的尺寸 kwarg -- `width` / `height` (`int` | `'stretch'` | `'content'` | `'auto'`), 以及 canary 独有的 `max_height` / `min_height` (只收正整数或 `None`; 上下限是像素数而非尺寸, 所以不接受关键字). 定义与校验在 `components_v3/base.py` 的 "Size scheme". 落地分两条路: 自己拼 `style` 的布局组件 (`Container` / `Row` / `Grid` / `Cell` / `Floating` / `Tabs` / `Dialog` / `Expander`) 走 `render.py` 的 `_bounds_style`, 其余 (含所有 widget 与 `Space` / `LogPanel`) 走 `_size_style`; 文本元素 (`Text` / `Markdown` / `Caption` / `Title`) 走它的薄封装 `_text_style` -- 同一份尺寸规则列表 (`_size_rules`) 再加一条可选的 `font-family`, 对应 `_HelpText` 的 `font_family` 字段 (静态, 顾名思义给"要按列对齐"的文本用, 常取 `sc.MONOSPACED`). `sc.MONOSPACED` 还会连带带上 `font_size` 的默认值 `MONOSPACED_SIZE` (`0.875em`, 即 Streamlit 的 code 字号): 等宽字体在同样像素下观感更大 (实测 'Cascadia Code' 相对页面字体宽度 +39% / x-height +6%, 宽度是大头), 所以 code 要降一档; 显式传 `font_size` 可覆盖, 而 `Title` 自带字号、不接这条默认值 (只对画在正文字号上的元素生效). 一个元素只能有一个 `style`, 所以 `_style_attr` 会把声明做 HTML 转义 (font 名里的引号否则会把属性提前截断). 两条规则: ① `max_height` 会连带 `overflow: auto` (封顶的盒子要能滚动, 与 `height=int` 同款), `min_height` 没有这个副作用; ② `height='stretch'` 胜出 -- 上下限被丢弃 (见 `_size_rule` 的提前返回). 注意 `Dialog` 的上下限落在面板 (`.st-dialog`) 上而不是根 (根是全屏背板), `Popover` 的根是触发器外壳所以不接这两个 kwarg (面板用 `panel_max_height`). `max_width` / `min_width` 尚未提供. 唯一的例外是 `Multiselect` 的 `'fixed'`: 它**不在**共享词汇里 (定义见 `components_v3/inputs.py` 的 `T.MultiselectHeight`), 语义是"触发器保持一行, 值不换行, 溢出的横向滚动", 由 `inputs.py` 自己翻译成 `_default_height` (传 `'fixed'` 时先转成 `None` 再交给 base, 因为 base 的校验只认标准关键字), 渲染时加 `st-multiselect--fixed`, 样式在 `60-misc.css`. 别的组件传 `'fixed'` 会被直接拒绝.
- **Multiselect 的选择顺序 = 勾选顺序**: 触发器显示的顺序、发给后端的 `value` 顺序、后端存下来的顺序, 都是勾选顺序 (勾上就追加到末尾, 取消就抽走). 服务端在 `_render_multiselect` 里按 `value` 的顺序出摘要, 并把 `value` 的字符串形式写进 `data-selected`; 前端 `scMultiselectSelection` (见 `30-overlays.js`) 维护这个有序列表 -- `data-selected` 是它的**初始种子** (所以刚打开页面、还没收到 `value` patch 时, 一次 `options` patch 也不会把已勾选的项丢掉), 之后每次 `value` patch 刷新它. 摘要里的标签用的是**渲染后的 markup** 而不是 `textContent` (否则 `:material/...:` 会退化成连字名纯文本).
- **`PathInput.candidates` 是"最近路径"记忆, `TextInput.candidates` 只是转发列表**: 两个字段同名但语义不同, 别混用. `TextInput` 收到什么就原样挂出去 (顺序也保留). `PathInput` 拿到**字面序列**时把它当种子, 建一个 `deque(maxlen=...)` 记忆 (`inputs.py` 的 `_candidate_capacity`: 至少 20; 更大的种子向上取整到十位, 23 -> 30): 每当 `value` 解析出真实路径 (提交 / 失焦 / `show()`) 就 `appendleft` 进去 (已存在的不重复、也不重排), 满了 (`maxlen`) 就把最旧的挤掉; 面板列的是 `sorted(...)` -- **style #1 字母序**, 记忆本身按"遇到的先后"排, 那是 TODO 里的 style #2. 传 `Property` 就完全不接管 (调用者自己维护), 传 `None` 仍然是没有面板. 注意 `TreeSelectWithInput` 现在**传** `candidates=[]` -- 盒子自己就是"最近路径"记录 (初值即 `start_directory`, 之后每解析出一个路径就长一条), 取代了它原来那个 `Recent` 下拉; `TreeSelectDualPaneWithInput` 仍然不传 (保留它自己的 `Recent` 实现) -- 别把这条默认行为顺手带到它身上; 见 `test/path_input_candidates_test.py`.
- **`width='content'` 要按"最宽的选项"算, 不是按当前值算**: `Selectbox` 的标签可能长短不一, 若按当前值取宽, 每次切换都会让触发器宽度跳动 (见 `test/selectbox_on_width_wrap.py`). 做法: 服务端把每个选项的 markdown 渲染进一个不可见的 sizer (`render.py` 的 `_render_selectbox`, 只在 `_width == 'content'` 时输出), `34-selectbox.css` 让 sizer 与触发器共用一个 grid 单元格, 于是"两者中更宽的那个"决定单元格宽度, 而浏览器替我们挑出最宽的选项 (含 `:material/...:` 图标的真实字宽). 三个关键点: ① sizer 必须是 `visibility: hidden` 而不是 `display: none` (后者量不到宽度); ② sizer 的 `width` 必须是 `auto`, 否则它会被自己该撑开的单元格约束住, 文本 wrap 后报出当前宽度 (这个坑很隐蔽, 是实测出来的); ③ 选项在运行期变化时, `20-selectbox.js` 的 `scRenderSelectboxOptions` 会同步重建 sizer 的内容. 注意 `Multiselect` 与 TextInput 目前都没接这套 (前者没有 `width='content'` 支持, 后者不按选项取宽).
- **Selectbox 的下拉框会逃离"裁剪祖先"**: `.st-selectbox-dropdown` 默认是 `position: absolute`, 贴在锚定它的 `.st-selectbox-control` 下面; 但只要祖先里有一个把 overflow 设成非 `visible` 的盒子 (任何被 `height` / `max_height` 封顶的容器, 以及 popover 面板 -- `--row` / `--menu` / `--above` 都算), 它就会被那个盒子在边界处裁断 (见 `test/selectbox_popover_overflow.py` 里 `TreeSelect(max_height=200)` 的 "Current location" 一例). 因此前端 (`20-selectbox.js` 的 `scPositionSelectboxDropdown`) 每次都往上找最近的裁剪祖先: 找到就把下拉框提升为 `position: fixed` 并加 `st-selectbox-dropdown--fixed` (`34-selectbox.css`), 用视口坐标重新定位 -- 于是它浮在那个盒子之上而不是被切断, 与 popover 面板本身逃离祖先的做法一致; 下方放不下就翻到上方打开, 并始终夹在视口与 `#app` 内容框内. 找不到裁剪祖先时保留原本的 `absolute` 定位 (这也是它跟 `width='content'` 的共同点: 那条 sizer 逻辑只在 `absolute` 那条路上测宽). 因为用的是视口坐标, 打开期间任何 `scroll` (捕获阶段) / `resize` 都要重新定位 (`40-inputs.js`).
- **TreeSelect 的位置栏与"来向高亮"**: 工具栏是 `[位置栏] [home] [refresh] [bucket] [mode]`, `home` 回到 `start_directory`. 位置栏这个 `Selectbox` 的选项是 **所有盘符在前 + 当前路径的祖先链在后** (`trees._location_options`; 盘符由 `os.listdrives()` 取一次缓存在 `_DRIVES`, POSIX 上为空, 因为那里链条本身就起于 `/`), 链的最后一节就是"你在哪". 另外, 面板记住"刚离开的是哪个文件夹" (`_came_from`), 回到上层时把**那一行**画上 `is-highlighted`; 客户端的点击高亮在每次重建 options 时都会丢, 所以这件事必须由服务端做: 行索引按节点记在 `_TreeNav.node_index` 里, `_focus_index` 再按路径对新列表复核一遍 (列表可能已变), 结果随 `options` patch 的 `focused` 字段下发 (`runtime.py` 的 broadcast), JS 重建行时贴 class (`10-helpers.js` 的 `scChoiceItemsHtml`). 跨多层的跳转 (点位置栏上很远的某一节, 或 `home`) 落不到那一行上, 就改标"通往它的那一行"; 因此 `_refresh_listing` 里 options 必须 `notify=True` 强发一次 patch, 否则选项没变时高亮传不过去.
- **截断了才提示的下拉项 (`st-truncate-help`)**: `Selectbox` 下拉里每一行的标签盒子都会把过长的文本截断, 这些盒子贴着 `st-truncate-help` (`render._render_selectbox` 的 `.st-selectbox-option-inner`; `20-selectbox.js` 重建行时也要带上). 客户端 (`90-help.js`) 在它**真的被截断时** (`scrollWidth > clientWidth`) 借 help tooltip 那套 pane 把它**自己的内容**显示出来 -- 那是元素已渲染的 markup, 所以 `:material/...:` 图标照旧显示, 也不必额外往下传一份文案. 与 `data-help` 的区别: 后者是固定的 markdown 文案 (widget 的 `help`)、可交互、且离开后留 200ms 宽限让指针能移到 pane 上; 前者是"截断了才提示"、**不可交互** (`pointer-events: none`)、鼠标一离开那一行就立刻消失, 并且 pane 摆到列表右侧、z-index 抬到所有面板之上 (`20-layouts.css` 里的 `1000100`; 逃逸过的下拉是 `1000050`, 菜单面板是 `1000060`) -- 免得挡住鼠标正要往下走的那些行, 或者被下拉 / 对话框盖住. 新增"截断了才提示"的地方沿用这个 class, 不要自己造 tooltip.
- **间距两个 token (hgap / vgap)**: 横向间距用 `--st-hgap` (8px, 有意比 Streamlit 的 16px 窄, 让并排的箱子读作一个聚簇), 纵向间距用 `--st-vgap` (16px, 与 Streamlit 一致). 二者都定义在 `runtime/static/css/01-base.css` 的 `:root`. 用 hgap 的: `Row` 子元素并排时, `Grid` 的列轨道, 横向 `Radio` / `CheckGroup` 的选项之间, tab 条上的 tab, `FloatingContainer` 聚簇内; 用 vgap 的: `#app`, `Container`, `Grid` 的行距与 `GridCell`, popover 面板, expander 正文, tab 面板 (`Row` 换行后两行之间也算 vgap). 属于控件自身尺度的间距 (按钮文案到图标, checkbox 框到文字) 不要套这两个 token, 保持字面值. 新增横向排布容器时记得改 `--st-hgap` 而不是写 16px; `Grid` 的列宽由服务端 `render.py` 的 `gap_px` 参与计算, 改 hgap 必须同步改它 (否则轨道加间距不再填满容器).
- **控件统一高度**: 按钮 (`Button` / `IconButton` / `Popover` 与 `MenuButton` 的触发器), 单行输入框 (`TextInput` 的输入部分), `NumberInput` 的盒子, `Selectbox` 的触发器, `SegmentedControl` 的轨道, 以及共用一块状态区的 `Callout` / `Spinner`, 共用一个高度 token `--st-control-height` (32px, 定义在 `runtime/static/css/01-base.css` 的 `:root`; 有意比 Streamlit 的 40px 矮 8px, 为的是让一行 / 一条工具栏里的框成为一条齐平的腰带). 新增这类"控件框"时用它做 `min-height`, 不要写死 40px; 会增高的控件 (多行按钮文案, 换行 alert) 靠 `min-height` 自然撑高. 注意 `min-height: var(...)` 会被复用该类的内层 (如 NumberInput 内层输入框) 继承, 所以内层要照现有 override 把 `min-height` 归零, 让外框拥有高度. 这条差异与实测值记在 `.trae/documents/pixel_fidelity_caveats.md`.
- **文本类组件统一字号 (即 `Callout` 的字号)**: `Text` / `Markdown` / `TextArea` 与 `Callout` 共用 `font-size: var(--st-base-font-size)` (16px, 定义在 `theme-*.css`; 就是正文字号, 也正是 Streamlit 画它们时用的那一档). `Text` / `TextArea` 早先写死过 14px, 已改齐 (`10-texts.css` 与 `30-inputs.css` 各有一条注释指回这里). 新增"读一段文字"的组件照此用 token, 别写死像素; 而 Button / Spinner / tab 标签这类**控件自身尺度**的字号不归这条管 (参照"控件统一高度"的取舍).
- **Markdown 在前端渲染**: 服务器只把 markdown 源文写进 `.st-md` / `.st-md-block` 占位符的 `data-md` 属性, 真正的解析由 `page.js` + 打包的 `markdown-it` 在浏览器完成 (与 Streamlit 的 react-markdown 一致). 因此 `render_markup` (行内) / `_render_paragraphs` (块级) 只负责出占位符; 新增承载 markdown 的元素时, 必须带上 `st-md` (或 `st-md-block`) 类, 否则 delta patch 与样式都会失配. 占位符**即便源文为空也照发** -- 它的类就是 `text` patch 用来判断"用哪个渲染器、落进哪个元素"的依据, 所以必须从首帧起就在. 纯文本走另一条路: `Text` 镜像 `st.text`, 按原文输出 (HTML 转义、不解析 markdown、保留空白), 占位符是 `.st-plain` (`render.py` 的 `_render_plain`), 前端按 `textContent` 换 (所以 patch 不经过 markdown 渲染器); `Markdown` 则先把多行源文 `dedent` + `strip` (`texts.py` 的 `_dedent_block`, 经 `sc.bind` 挂在 `text` 上, 所以后续每次变更都生效, 也让"空文本"的判定看到整理后的结果). Streamlit 自有的 `:color[..]` / `:material/..:` 扩展和 typographer (` -> ` → `→` 等) 也在 `page.js` 里以插件形式实现; 另一套符号库 `:smile:` 这类 **emoji 短码**同样认 -- 它走 `/static/emoji-shortcodes.js` 那张表 (`window.SC_EMOJI`, 由 `test/gen_emoji_shortcodes.py` 生成), 命中的名字替换成裸字符 (Streamlit 的 remark-emoji 就是这么渲染的: 没有外层元素、没有 `role="img"`), 表里没有的名字原样留着; 名字要按 Streamlit 的口径来, 比如 `:+1:` 有而 `:thumbsup:` 没有 (后者只是它的 keyword), 所以 `\+1` / `-1` 在规则里要单独列出来 (`\w` 都不含). 同一个 inline 规则还认四个**效果**标记 `:bold[..]` / `:italic[..]` / `:strike[..]` / `:underline[..]` -- 前三个推的就是 markdown-it 自己那对 token (`<tag>_open` / `<tag>_close`, tag 放在 token 上), 所以结果与 `**x**` / `*x*` / `~~x~~` 完全一致; `underline` 在 markdown 里没有记法, 于是给 tag `u`. 标记可以任意嵌套 (`:blue[:italic[a :bold[b]]]`), 闭合方括号取的是**配平**的那一个 (`scMarkEnd` 深度计数, 反斜杠转义下一个字符, 所以 `\[` / `\]` 是字面方括号) -- 别用 `[^\]]*` 之类的正则去截, 那会在第一个 `]` 处断掉; 括号不配平时整个标记按普通文本走. 另外 `sc.set_page_config(..., dunder_literal=True)` 是个实验开关 (默认关): 开了之后 `__x__` 不再读作加粗, 文字里的 `__init__` / `__name__` 不会被误变粗体, 加粗只剩 `**x**` 与 `:bold[x]` 两种写法. 实现是在 token 流上把 `markup === '__'` 的 `strong` 还原成字面 `__` (`50-markdown.js` 的 `st_dunder_literal`), 而不去重写 markdown-it 那套强调规则; `_italic_` 与代码段 / 围栏里的内容都不受影响. 开关由 `render_page` 落在 `#app` 的 `data-dunder-literal` 属性上, 装载期读一次.
- **`streamlit` 是可选依赖**: v3 内核与运行时 (`kernel` / `components_v3` / `runtime`) 完全不依赖 streamlit, 所以 `import streamlit_canary` 在没有 streamlit 的环境下也必须成功 (第三方直接安装本包不会带上 streamlit). 需要 streamlit 的 v1/v2 模块一律从 `streamlit_canary/_streamlit.py` 取 `st` (`from ._streamlit import st`; 子包按层级写 `..` / `...`), **不要**写顶层 `import streamlit as st`. 该对象是个惰性代理: 首次属性访问才真正 `import streamlit`, 缺失时抛出带 `uv add streamlit` 提示的 `ImportError`. 因此**不要在模块顶层对 `st` 求值** (如 `alias = st.container` / `partial(st.button, ...)` / `st.session_state[...]` / 类型别名), 否则会在导入期就触发导入 -- 三种处理: ① 包成函数 (`components/button.py:long_button`, `components/container.py:column`); ② 放进 `if tp.TYPE_CHECKING:` 分支, 运行期退化为 `tp.Any` (`components/_typing.py`, `page.py` 的 `StreamlitPage`); ③ 交给惰性判断 (如 `session.py` 顶层那几行被 `_is_running_in_streamlit()` 挡住, 没装 streamlit 时必然为假, 所以不会触发). 只有 `if __name__ == '__main__':` 守卫下的代码可以例外 (`components/scope.py`).
- **Web 服务**: 用 Starlette + Uvicorn (HTTP 页面 + WebSocket 事件/delta), 不用 FastAPI.
- **v3 服务默认绑定所有网卡**: `serve()` (`runtime/server.py`) 默认 `host='0.0.0.0'`, 所以应用既能在 `localhost:<port>` 打开, 也能在局域网里用 `http://<本机局域网 IP>:<port>` 打开; `runner.run` 启动时会同时打印这两个 URL (`_get_local_ip` 取本机局域网地址, 对应 Streamlit 的 "Local URL / Network URL"). 只想留给自己用时传 `sc.run(..., host='127.0.0.1')`. 前端 WebSocket 用的是 `ws://${location.host}/ws` (`00-connection.js`), 因此页面从哪个地址打开, 事件就回到哪个地址, 不需要额外配置.
- **Web 服务器非阻塞**: 必须非阻塞启动, 可用 StopCommand 停止.
- **Python 3.12+**: 使用现代语法 (`type | type` 联合, `match` 等).

## 9. Kernel 事件约定 (Property / Signal)

示例:

```python
count = sc.Property(0)

@count.on_change                      # 无参 handler
def aaa(): ...

@count.on_change.partial('x')         # 绑定静态参数
def bbb(word): ...

@count.on_change.partial(sc._self)    # 收到 Property handle
def ccc(prop): ...

@count.on_change.partial(sc._value)   # 收到当前值
def ddd(value): ...
```
