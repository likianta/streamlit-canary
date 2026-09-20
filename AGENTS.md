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
│   │   └── trees.py          # 自研文件夹浏览器 (TreeSelect 家族)
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
├── test/                     # 测试与演示 (你可以在本目录下根据需要创建新的测试脚本)
│   ├── event_driven_system/        # v3 事件驱动测试
│   │   ├── components_v3_demo.py   # 纯 Python 组件树 / 信号演示
│   │   └── ...
│   ├── pixel_fidelity/       # UI 像素级对齐的试验脚本
│   └── ...
├── references/               # 参考资源
│   ├── asa_gui/              # 原版基于 Streamlit 的演示应用, 运行在 localhost:2204
│   ├── pdf_watermaker/       # 原版基于 Streamlit 的演示应用, 运行在 localhost:2210
│   ├── pyproject_manager/    # 原版基于 Streamlit 的演示应用, 运行在 localhost:2206
│   ├── streamlit/            # Streamlit 源码
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
python test/event_driven_system/pyproject_manager_copy/app.py     # :2207

# 运行最小 v3 demo (计数器, 参考用法见其 docstring)
python test/event_driven_system/demo_click_counter.py             # :2201

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

> 注意: 全量 `ty check streamlit_canary/` 会对 v1 老模块报出若干 **既存** 问题
> (`components/filelist.py`, `components/radio.py`, 
> `components/tree_select/wrappers.py`, `__main__.py`). 改动 v3 相关代码时,
> 建议只检查目标包, 例如:
> `ty check streamlit_canary/components_v3/ streamlit_canary/runtime/`

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
2208: Depsland AppBuilder 原版应用 (暂未开始).
2209: Depsland AppBuilder 副本应用 (暂未开始).
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

## 7. 架构约束

- **State 和 Components 统一读写风格**: `.get()` / `.set()` / `__getitem__` / `__setitem__` / `on_change`, 降低理解负担.
- **组件属性**: 可响应字段用 `Property` (如 `Text.text`, `Selectbox.value`), 静态配置用 `_` 前缀属性(如 `Button._type`).
- **v2/v3 命名空间**: v2/v3 的新元素不直接暴露在 `__init__.py`, 用 `components_v3` 作为 v3 命名空间 (如 `sc.v3.Button`).
- **`references/` 只读**: `references/` 目录 (含其中以软链接形式挂载的参考项目) 对 agent 是**只读**的, 不要修改其中的任何文件; 只可读取作为参考.
- **组件复用**: 多个组件共用的字段 / 逻辑抽到 `components_v3/_shared.py` 的私有基类 (`_HasText` / `_Labeled` / `_OptionsWidget` / `_TextVisible`). 组件字段在 `__init__` 中用 `_prop(default, source)` 声明, 以同时支持传入普通值或 `Property`.
- **`label_visibility` 的四个值与 `auto` 默认**: 带 label 的组件 (继承 `_Labeled` / `_OptionsWidget` 的那些) 都接受 `label_visibility`, 取值见 `components_v3/inputs.py` 的 `T.LabelVisibility`: `'auto'` (默认) | `'visible'` | `'hidden'` | `'collapsed'`. `'auto'` 在渲染期由 `runtime/render.py` 的 `_widget_label_html` 判定一次: label 有内容就等同 `'visible'`, 否则等同 `'collapsed'` (空 label 否则仍会占住标签行的 24px + 4px). 注意 `label_visibility` 是静态字段而 `label` 是可绑定的, 所以 `'auto'` 按渲染那一刻的 label 判定, 之后 label 变化不会重新判定 (要动态得先给它加 patch 通道). 新增带 label 的组件请继承 `_Labeled`, 不要自己拼 label 的 HTML -- `_widget_label_html` 是唯一的 label 渲染入口.
- **组件按 Streamlit 分类分模块**: `components_v3/` 下按 Streamlit API reference 的分类分文件, 模块名统一用复数形式 (`data` / `status` 单复数同形) -- `texts` (Text elements) / `data` / `charts` / `buttons` + `inputs` (Input widgets 一分为二) / `layouts` (Layouts and containers) / `status`; 分类表与官方对照见 `components_v3/__init__.py` 的模块 docstring, 原始分类清单在 `references/streamlit_api_reference_catagory.html`. 组件与 Streamlit 的对应关系 (以及我们自研的部分) 以该 docstring 为准.
- **前端资源独立存放**: CSS / JS 放在 `runtime/static/` (`markdown-it.min.js` / `theme-*.css` / `fonts`), 用 `lk_utils.fs.load(fs.here(...), 'plain')` 在模块加载期读入; 不要在 Python 里内联大段 CSS / JS. 因此 **改动这些文件后必须重启服务**.
- **样式表与脚本按组件分块**: `page.css` / `page.js` 这两个"页面级包"不再各是一个大文件, 而是分别由 `runtime/static/css/*` 与 `runtime/static/js/*` 下的分块文件按固定顺序拼成 (`render.py` 的 `_PAGE_CSS` / `_PAGE_JS` 列表就是唯一权威的顺序, 数字前缀与之一致). 拼接顺序即 CSS 层叠顺序, 所以要**按列表改**, 不要随手调整文件名或顺序; 其它文档 / 注释里提到的 "`page.css`" / "`page.js`" 都指这两个包, 按分块文件名 (如 `35-choice.css`) 或选择器名去 grep 即可.
- **组件尺寸与高度上下限**: 所有组件都接受统一的尺寸 kwarg -- `width` / `height` (`int` | `'stretch'` | `'content'` | `'auto'`), 以及 canary 独有的 `max_height` / `min_height` (只收正整数或 `None`; 上下限是像素数而非尺寸, 所以不接受关键字). 定义与校验在 `components_v3/base.py` 的 "Size scheme". 落地分两条路: 自己拼 `style` 的布局组件 (`Column` / `Row` / `Grid` / `Cell` / `Floating` / `Tabs` / `Dialog` / `Expander`) 走 `render.py` 的 `_bounds_style`, 其余 (含所有 widget 与 `Space` / `LogPanel`) 走 `_size_style`. 两条规则: ① `max_height` 会连带 `overflow: auto` (封顶的盒子要能滚动, 与 `height=int` 同款), `min_height` 没有这个副作用; ② `height='stretch'` 胜出 -- 上下限被丢弃 (见 `_size_rule` 的提前返回). 注意 `Dialog` 的上下限落在面板 (`.st-dialog`) 上而不是根 (根是全屏背板), `Popover` 的根是触发器外壳所以不接这两个 kwarg (面板用 `panel_max_height`). `max_width` / `min_width` 尚未提供. 唯一的例外是 `Multiselect` 的 `'fixed'`: 它**不在**共享词汇里 (定义见 `components_v3/inputs.py` 的 `T.MultiselectHeight`), 语义是"触发器保持一行, 值不换行, 溢出的横向滚动", 由 `inputs.py` 自己翻译成 `_default_height` (传 `'fixed'` 时先转成 `None` 再交给 base, 因为 base 的校验只认标准关键字), 渲染时加 `st-multiselect--fixed`, 样式在 `60-misc.css`. 别的组件传 `'fixed'` 会被直接拒绝.
- **Multiselect 的选择顺序 = 勾选顺序**: 触发器显示的顺序、发给后端的 `value` 顺序、后端存下来的顺序, 都是勾选顺序 (勾上就追加到末尾, 取消就抽走). 服务端在 `_render_multiselect` 里按 `value` 的顺序出摘要, 并把 `value` 的字符串形式写进 `data-selected`; 前端 `scMultiselectSelection` (见 `30-overlays.js`) 维护这个有序列表 -- `data-selected` 是它的**初始种子** (所以刚打开页面、还没收到 `value` patch 时, 一次 `options` patch 也不会把已勾选的项丢掉), 之后每次 `value` patch 刷新它. 摘要里的标签用的是**渲染后的 markup** 而不是 `textContent` (否则 `:material/...:` 会退化成连字名纯文本).
- **`width='content'` 要按"最宽的选项"算, 不是按当前值算**: `Selectbox` 的标签可能长短不一, 若按当前值取宽, 每次切换都会让触发器宽度跳动 (见 `test/selectbox_on_width_wrap.py`). 做法: 服务端把每个选项的 markdown 渲染进一个不可见的 sizer (`render.py` 的 `_render_selectbox`, 只在 `_width == 'content'` 时输出), `34-selectbox.css` 让 sizer 与触发器共用一个 grid 单元格, 于是"两者中更宽的那个"决定单元格宽度, 而浏览器替我们挑出最宽的选项 (含 `:material/...:` 图标的真实字宽). 三个关键点: ① sizer 必须是 `visibility: hidden` 而不是 `display: none` (后者量不到宽度); ② sizer 的 `width` 必须是 `auto`, 否则它会被自己该撑开的单元格约束住, 文本 wrap 后报出当前宽度 (这个坑很隐蔽, 是实测出来的); ③ 选项在运行期变化时, `20-selectbox.js` 的 `scRenderSelectboxOptions` 会同步重建 sizer 的内容. 注意 `Multiselect` 与 TextInput 目前都没接这套 (前者没有 `width='content'` 支持, 后者不按选项取宽).
- **间距两个 token (hgap / vgap)**: 横向间距用 `--st-hgap` (8px, 有意比 Streamlit 的 16px 窄, 让并排的箱子读作一个聚簇), 纵向间距用 `--st-vgap` (16px, 与 Streamlit 一致). 二者都定义在 `runtime/static/css/01-base.css` 的 `:root`. 用 hgap 的: `Row` 子元素并排时, `Grid` 的列轨道, 横向 `Radio` / `CheckGroup` 的选项之间, tab 条上的 tab, `FloatingContainer` 聚簇内; 用 vgap 的: `#app`, `Container`, `Grid` 的行距与 `GridCell`, popover 面板, expander 正文, tab 面板 (`Row` 换行后两行之间也算 vgap). 属于控件自身尺度的间距 (按钮文案到图标, checkbox 框到文字) 不要套这两个 token, 保持字面值. 新增横向排布容器时记得改 `--st-hgap` 而不是写 16px; `Grid` 的列宽由服务端 `render.py` 的 `gap_px` 参与计算, 改 hgap 必须同步改它 (否则轨道加间距不再填满容器).
- **控件统一高度**: 按钮 (`Button` / `IconButton` / `Popover` 与 `MenuButton` 的触发器), 单行输入框 (`TextInput` 的输入部分), `NumberInput` 的盒子, `Selectbox` 的触发器, `SegmentedControl` 的轨道, 以及共用一块状态区的 `Callout` / `Spinner`, 共用一个高度 token `--st-control-height` (32px, 定义在 `runtime/static/css/01-base.css` 的 `:root`; 有意比 Streamlit 的 40px 矮 8px, 为的是让一行 / 一条工具栏里的框成为一条齐平的腰带). 新增这类"控件框"时用它做 `min-height`, 不要写死 40px; 会增高的控件 (多行按钮文案, 换行 alert) 靠 `min-height` 自然撑高. 注意 `min-height: var(...)` 会被复用该类的内层 (如 NumberInput 内层输入框) 继承, 所以内层要照现有 override 把 `min-height` 归零, 让外框拥有高度. 这条差异与实测值记在 `.trae/documents/pixel_fidelity_caveats.md`.
- **Markdown 在前端渲染**: 服务器只把 markdown 源文写进 `.st-md` / `.st-md-block` 占位符的 `data-md` 属性, 真正的解析由 `page.js` + 打包的 `markdown-it` 在浏览器完成 (与 Streamlit 的 react-markdown 一致). 因此 `render_markup` (行内) / `_render_paragraphs` (块级) 只负责出占位符; 新增承载 markdown 的元素时, 必须带上 `st-md` (或 `st-md-block`) 类, 否则 delta patch 与样式都会失配. Streamlit 自有的 `:color[..]` / `:material/..:` 扩展和 typographer (` -> ` → `→` 等) 也在 `page.js` 里以插件形式实现.
- **Web 服务**: 用 Starlette + Uvicorn (HTTP 页面 + WebSocket 事件/delta), 不用 FastAPI.
- **Web 服务器非阻塞**: 必须非阻塞启动, 可用 StopCommand 停止.
- **Python 3.12+**: 使用现代语法 (`type | type` 联合, `match` 等).

## 8. Kernel 事件约定 (Property / Signal)

- **`on_change` 不默认传参**: `Property.set()` 触发时调用 `Signal.emit()`, **不会** 把 Property 自身作为第一个参数传给 handler.
- **Signal 的参数声明**: 构造 `Signal` 时用类型声明 `emit()` 的载荷 -- `*args` 是位置参数, `**kwargs` 是命名参数 (命名参数也可以按位置顺序传入). 例如 `Signal(bool, reason=str)` 的 `emit(ok, reason='...')` 和 `emit(ok, '...')` 等价; handler 收到的始终是按声明顺序排列的位置参数. 不声明参数则是自由形式, `emit()` 原样透传 (内置的 `Signal()` 都是这种, 因为它们不携带载荷). 声明之后, 参数缺失 / 多传 / 拼错关键字都会在 `emit()` 处立即抛 `TypeError`.
- **按需注入 owner**: 用 `Signal.partial(...)` 绑定特殊标记来拿到 owner:
  - `sc._self` → handler 收到 owner (触发变更的 Property handle)
  - `sc._value` → handler 收到 owner 的当前值 (`owner.get()`)
  - 普通值原样绑定在参数列表最前面
- **立即触发**: `@sig.emit_now` 注册 handler 并立刻 emit 一次; 若同时需要注入 owner, 用 `@sig.partial(sc._self).emit_now`.
- **Property 可独立使用**: `count = sc.Property(0)` 是自包含的响应式值 (`get` / `set` / `on_change`).
- **挂到 StateV2 / Component 上**: 在 `__init__` 里赋值成实例属性 (如 `self.count = sc.Property(0)`); `PropertyHost._iter_properties()` 通过扫描实例 `__dict__` 发现它们, 因此每个实例各持一份, 互不共享. (类属性写法也能用, 但会被该类所有实例共享, 只适合单实例场景.)
- **按注解声明字段**: `PropertyHost` (StateV2 / Component) 在 `__init__` 时扫描类注解, 为 `sc.Property[...]` / `sc.Signal[...]` 注解的字段分别创建实例自己的 Property / Signal, 因此 `__init__` 里不必再写一遍 (仍可写, 后写的会覆盖). 只认 `Property` / `Property[T]` 与 `Signal` / `Signal[T]`, 普通注解 (如 `current_scope: str`) 不参与; `Signal[T]` 等价于 `Signal(T)`, 多个位置参数写成 `Signal[T, U]`. 类体内的同名值给 `Property` 作默认值 (`age: sc.Property[int] = 0`), 给 `Signal` 则是声明它的参数 (`changed: sc.Signal = sc.Signal(bool, reason=str)`); 类级别的句柄只贡献声明部分 (default / 参数), 不会把句柄本身交给实例 (那会被所有实例共享). 子类的 `__init__` 记得调用 `super().__init__()`.
- **值或绑定二选一**: 构造参数用 `p.set_or_bind(x)` 统一处理 -- `x` 是 `Property` 就 `bind` (此后跟随其变化), 否则 `set`. `sc.bind(source, transform)` 用于创建匿名绑定 Property, 例如 `v3.Button('Go', enabled=sc.bind(state.busy, lambda x: not x))`.
- **`sc.bind` 的源里可以放 Signal**: `sc.bind((prop, signal), transform)` 中的 Signal 是**触发器**, 不是值 -- 它一 emit 就强制重算并强制通知; `transform` 只收到 Property 的值 (按声明顺序), Signal 不占位置 (所以加一个 Signal 不会让 `x[0]` / `x[1]` 错位). 典型用途: 选项值不变但渲染文案变了 (见下一条), 例如 `options=sc.bind((state.name_to_project, state.project_revamped), lambda x: list(x[0].keys()))`. 单独一个 Signal (没有 Property 陪它) 是用法错误, 会抛 `TypeError`.
- **强制通知会穿透绑定链**: `p.set(v, notify=True)` 不只表示"值没变也通知一次", 而是一次 *forced* 通知 -- 含义是"值以外的东西变了, 请重画". 它会沿绑定链一路传下去 (每一跳都用 `notify=True` 同步自己的目标), 所以 `state.x.set(v, True)` 能让**间接**绑定、甚至隔了好几跳的 widget 属性重新发 patch. 这一跳是必需的: widget 总是把传入的 property 用 `set_or_bind` 绑到自己的 property 上, 于是"你给的 property"和"runtime 实际监听/打 patch 的 property"之间隔着至少一跳. 两个用例: ① 就地改了 dict (`state.d.get()['k'] = v; state.d.set(state.d.get(), True)`) -- 同一个对象比较相等, 不强制的话没有任何下游会动; ② 渲染依赖了值以外的状态, 比如 `Radio(format=...)` 读的是版本号, 而版本号不在选项值里. 注意: `notify=None` 的普通变更不会被强制, 所以"没变化就什么都不做"这个默认行为不受影响.
- **批处理里监听方的异常延后抛出**: `with sc.pending_updates():` 结束时, 某个监听方抛错不会中断这一批的通知 -- 错误先收集, 等所有 property 都被通知到之后再抛 (只有一个时原样抛出, 多个合并成 `ExceptionGroup`), 这样一个坏掉的监听方不会饿死其余的. 若 block 自身也抛了错, 批处理侧的错只作为 note (`__notes__`) 附在它上面, 不会把它顶掉.

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

## 9. 新增一个 v3 组件的流程

一个 v3 组件通常涉及以下几处改动:

1. `components_v3/<分类>.py` -- 定义 class (按字母序插入, 优先复用 `_shared.py` 的私有基类); 在 `components_v3/__init__.py` 里导出. 分类怎么选见 §7 "组件按 Streamlit 分类分模块".
2. `runtime/render.py` -- 新增 `_render_xxx(comp)`, 并在 `_render()` 的分发链里加一个 `isinstance(comp, Xxx)` 分支 (必须放在最后的兜底分支之前).
3. `runtime/static/page.css` -- 组件的样式.
4. `runtime/static/page.js` -- 需要回传事件时加发送函数 (参照 `scSendChange` / `scSendCheck`); 需要响应 delta 时, 在 patch 分支里按 `el.classList.contains('st-xxx')` 处理.

协议约定:

- 前端 → 后端: `{"type":"event","id":"<comp-id>","event":"click"}` 或
  `{"type":"event","id":"<comp-id>","event":"change","value":...}`
- `Runtime.on_event()` 目前只识别 `click` (→ 组件的 `on_click`) 与
  `change` (→ 组件的 `value` Property); 其它事件类型需要在这里扩展.
- 后端 → 前端: `{"type":"patch","id":"<comp-id>","prop":"<prop-name>","value":...}`.
  `page.js` 已处理的 prop: `text` / `label` / `enabled` / `visible` /
  `options` (附带 `formatted` 显示文案) / `value` / `rows`.
