# AGENTS.md

> 对 AI agent 的项目指引. 每当 agent 进入此仓库工作时, 请先阅读本文档.

## 1. 项目概况

**Streamlit Canary** (`streamlit-canary`) 是对 Streamlit 的二次开发, 扩展了原版的组件库, 并实现了一套基于事件驱动的运行时. 开发者用纯 Python 写组件树, 运行时负责渲染 HTML, 路由事件, 推送 delta patch, 前端局部更新 DOM, 无需页面刷新.

- **语言**: Python 3.12 及以上
- **版本**: 0.4.0a10
- **包管理**: uv
- **代码风格**: ruff (line-length=80, single-quote, skip-magic-trailing-comma)
- **类型检查**: ty check
- **运行脚本**: `python ...` (已设置 `PYTHONPATH=.;src;lib;.venv/Lib/site-packages`)

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
│   │   ├── property.py       # Property: 带 get/set/on_change 的响应式属性
│   │   ├── signal.py         # Signal: 事件信号 (partial / emit_now)
│   │   ├── special_value.py  # sc._self / sc._value: Signal.partial 的特殊标记
│   │   └── state.py          # PropertyHost / StateV2: 状态容器
│   ├── components_v3/        # v3 事件驱动组件 (纯 Python, 无 Streamlit 依赖)
│   │   ├── base.py           # Component 基类: 组件树, 上下文栈, 注册到 runtime
│   │   └── widgets.py        # 内置组件 + 共享私有基类 (见 §3 组件清单)
│   ├── runtime/              # 事件驱动运行时
│   │   ├── runtime.py        # Runtime: 持久组件树 + 事件路由 + delta 广播
│   │   ├── render.py         # 组件树 → HTML
│   │   ├── server.py         # Starlette 应用 + WebSocket 端点
│   │   └── static/           # 前端资源: page.css / page.js / markdown-it.min.js / theme-*.css / 字体
│   ├── components/           # v1 组件 (基于 Streamlit)
│   ├── components_v2/        # v2 组件 (过渡版本)
│   ├── session.py            # v1 session state 管理 (init_state / init_state_v2)
│   └── runner.py             # 传统 Streamlit 子进程启动器 (legacy)
├── test/                     # 测试与演示
│   ├── event_driven_system/        # v3 事件驱动测试
│   │   ├── demo_click_counter.py   # 计数器 demo (最小可运行示例)
│   │   ├── components_v3_demo.py   # 纯 Python 组件树 / 信号演示
│   │   └── pyproject_manager_copy/ # pyproject-manager 的 v3 重写版 (软链接, 运行在 localhost:2207)
│   ├── pixel_fidelity/       # UI 像素级对齐的试验脚本
│   └── ...
├── references/               # 参考资源
│   ├── pyproject_manager/    # 原版基于 Streamlit 的演示应用, 运行在 localhost:2206
│   ├── streamlit/            # Streamlit 源码
│   └── ...                   # 截图, 参考图等
├── .trae/documents/          # 设计/路线图文档 (event_driven_streamlit_roadmap.md) 与像素对比差异说明 (pixel_fidelity_caveats.md)
├── pyproject.toml            # 项目配置
├── readme.md                 # 简要说明 (session state / v3 用法)
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

> 注意: 全量 `ty check streamlit_canary/` 会对 v1 老模块报出若干**既存**问题
> (`components/filelist.py`、`components/radio.py`、
> `components/tree_select/wrappers.py`、`__main__.py`). 改动 v3 相关代码时,
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
2210...2229: 暂未定义, 未来会根据需要添加.
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

在与 agent 交流 UI 交互和视觉要求时, **纯文字描述往往不够精确**. 推荐使用 **伪代码 (pseudo-code)** 来描述交互操作和断言.

### 4.1 为什么用伪代码

- 文字描述容易遗漏细节 (如 "hover 时背景应该是灰色" -- 哪个元素的灰色? 和谁对齐?)
- 伪代码可以精确表达:
  - **操作序列**: 先做什么, 再做什么
  - **目标元素**: 通过属性或层级定位
  - **断言条件**: 具体的 CSS 属性值, 几何关系
- Agent 可以直接把伪代码翻译为浏览器自动化行为

### 4.2 伪代码示例

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

### 4.3 Agent 工作流

当用户提供伪代码时, agent 应该:

1. **解析伪代码**: 识别操作序列, 目标元素, 断言条件
2. **采集数据**: 用 `browser_evaluate` 在原版 (`:2204` / `:2206`) 和副本 (`:2205` / `:2207`) 分别采集断言处的实际值
3. **对比分析**: 找出差异
4. **修复代码**: 按需改以下位置 --
   - `components_v3/widgets.py` -- 组件定义 / 属性
   - `runtime/render.py` -- HTML 结构
   - `runtime/static/page.css` -- 样式
   - `runtime/static/page.js` -- 前端交互 (事件回传 / delta patch)
5. **重新验证**: 重启服务 (前端资源在启动时读入, 改动后必须重启), 再次采集数据, 确认所有 assert 通过

### 4.4 像素对比测试前必读

在跑 `./test/pixel_fidelity/` 下的任何对比测试之前 (以及在据其结果判断 "这算不算 bug" 之前), 先读一遍 `.trae/documents/pixel_fidelity_caveats.md`.

该文档列出我们**有意为之**的差异 (例如: SelectBox 展开后, 用主题色高亮当前已选项; NumberInput 变窄时 stepper 转为 "上加下减" 的竖排布局), 以及**待对齐**的问题 (条目带 `TODO:` 前缀). 与 Streamlit 不一致的地方都先在这里对号入座: 不要把预期差异当成 bug 去 "修", 也不要把待对齐项当成预期差异而放过.

## 5. 工具链

- 使用 `python ...` 运行脚本 (已配置 `PYTHONPATH`,不需要 `sys.path.append`).
- 使用 `uv sync` 同步依赖, 使用 `uv` 管理 `pyproject.toml` 中的依赖.
- 使用 `ty check` 检查类型错误.
- 使用 `ruff check` 检查代码风格, 使用 `ruff format` 格式化代码.
- 每当完成修改后, 运行 `ty check`、`ruff check`、`ruff format` 确认无误.

## 6. 代码风格

- 优先使用 `format` 而不是 `f-string`.
- 代码中使用全英文注释, 不要有中文注释.
- 不需要在入口脚本的顶部添加 `sys.path.append(...)`. 因为我们已经设置好了环境变量 (`PYTHONPATH=.;src;lib;.venv/Lib/site-packages`).
- 不要在代码中添加 `from __future__ import annotations`.
- 每行代码不超过 80 字符 (见 `pyproject.toml:[tool.ruff]:line-length`).
- import 使用 force-single-line 风格 (见 `pyproject.toml:[tool.ruff.lint.isort]`).
- 字符串使用单引号 (见 `pyproject.toml:[tool.ruff.format]:quote-style`).
- 同一模块内的 class 按字母序排列 (私有基类因为要先于使用者定义, 可集中放在文件前部, 如 `components_v3/widgets.py`).
- 在代码注释 (`#` 开头的注释), `print(...)` 以及 `Exception(...)` 中使用小写字母开头的句子. 在函数注解 (docstring) 以及 triple-quoted strings 中, 使用规范的大小写格式.

## 7. 架构约束

- **State 和 Components 统一读写风格**: `.get()` / `.set()` / `on_change` / `__set__` / `__setitem__`, 降低理解负担.
- **组件属性**: 可响应字段用 `Property` (如 `Text.text`, `Selectbox.value`), 静态配置用 `_` 前缀属性(如 `Button._type`).
- **width / height 统一 scheme**: 尺寸在 `Component` 基类收口 (对齐 Streamlit 的 `layout_utils.py`): 每个组件都接受 `width` / `height`, 取值是 `int` (px) 或 `'stretch'` / `'content'` / `'auto'`; `None` 表示"用组件自己的默认值". 组件通过类属性 `_default_width` / `_default_height` 声明默认 (如 `Button = 'content'`, `TextInput = 'stretch'`, `Text` / `Caption` / `Title` = `'auto'`), 设为 `None` 表示该组件不参与尺寸 scheme. 基类把最终值存到 `comp._width` / `comp._height`; 渲染层用 `render.py` 的 `_size_style(comp)` (输出 `style` 属性, 同时处理 width 与 height) 或 `_width_style(comp)` (只处理 width, 供 `TextArea` 这类把高度放在内层元素的组件使用). 需要特殊语义的组件 (如 `Dialog` 用 `small` / `medium` / `large` 语义尺寸, `Column` 用 flex weight) 自行在 `__init__` 里解析并覆盖 `self._width`.
- **不使用 metaclass**: 因为 metaclass 会增加理解负担, 而且在当前实现中, 它的使用是不透明的.
- **v2/v3 命名空间**: v2/v3 的新元素不直接暴露在 `__init__.py`, 用 `components_v3` 作为 v3 命名空间 (如 `sc.v3.Button`).
- **`references/` 只读**: `references/` 目录 (含其中以软链接形式挂载的参考项目) 对 agent 是**只读**的, 不要修改其中的任何文件; 只可读取作为参考.
- **组件复用**: 多个组件共用的字段 / 逻辑抽到 `components_v3/widgets.py` 的私有基类 (`_HasText` / `_Labeled` / `_OptionsWidget` / `_TextVisible`). 组件字段在 `__init__` 中用 `_prop(default, source)` 声明, 以同时支持传入普通值或 `Property`.
- **前端资源独立存放**: CSS / JS 放在 `runtime/static/` (`page.css` / `page.js` / `markdown-it.min.js` / `theme-*.css`), 用 `lk_utils.fs.load(fs.here(...), 'plain')` 在模块加载期读入; 不要在 Python 里内联大段 CSS / JS. 因此**改动这些文件后必须重启服务**.
- **Markdown 在前端渲染**: 服务器只把 markdown 源文写进 `.st-md` / `.st-md-block` 占位符的 `data-md` 属性, 真正的解析由 `page.js` + 打包的 `markdown-it` 在浏览器完成 (与 Streamlit 的 react-markdown 一致). 因此 `render_markup` (行内) / `_render_paragraphs` (块级) 只负责出占位符; 新增承载 markdown 的元素时, 必须带上 `st-md` (或 `st-md-block`) 类, 否则 delta patch 与样式都会失配. Streamlit 自有的 `:color[..]` / `:material/..:` 扩展和 typographer (` -> ` → `→` 等) 也在 `page.js` 里以插件形式实现.
- **Web 服务**: 用 Starlette + Uvicorn (HTTP 页面 + WebSocket 事件/delta), 不用 FastAPI.
- **Web 服务器非阻塞**: 必须非阻塞启动, 可用 StopCommand 停止.
- **Python 3.12**: 使用现代语法 (`type | type` 联合, `match` 等).

## 8. Kernel 事件约定 (Property / Signal)

- **`on_change` 不默认传参**: `Property.set()` 触发时调用 `Signal.emit()`, **不会**把 Property 自身作为第一个参数传给 handler.
- **Signal 的参数声明**: 构造 `Signal` 时用类型声明 `emit()` 的载荷 -- `*args` 是位置参数, `**kwargs` 是命名参数 (命名参数也可以按位置顺序传入). 例如 `Signal(bool, reason=str)` 的 `emit(ok, reason='...')` 和 `emit(ok, '...')` 等价; handler 收到的始终是按声明顺序排列的位置参数. 不声明参数则是自由形式, `emit()` 原样透传 (内置的 `Signal()` 都是这种, 因为它们不携带载荷). 声明之后, 参数缺失 / 多传 / 拼错关键字都会在 `emit()` 处立即抛 `TypeError`.
- **按需注入 owner**: 用 `Signal.partial(...)` 绑定特殊标记来拿到 owner:
  - `sc._self` → handler 收到 owner (触发变更的 Property handle)
  - `sc._value` → handler 收到 owner 的当前值 (`owner.get()`)
  - 普通值原样绑定在参数列表最前面
- **立即触发**: `@sig.emit_now` 注册 handler 并立刻 emit 一次; 若同时需要注入 owner, 用 `@sig.partial(sc._self).emit_now`.
- **Property 可独立使用**: `count = sc.Property(0)` 是自包含的响应式值 (`get` / `set` / `on_change`).
- **挂到 StateV2 / Component 上**: 在 `__init__` 里赋值成实例属性 (如 `self.count = sc.Property(0)`); `PropertyHost._iter_properties()` 通过扫描实例 `__dict__` 发现它们, 因此每个实例各持一份, 互不共享. (类属性写法也能用, 但会被该类所有实例共享, 只适合单实例场景.)
- **按注解声明字段**: `PropertyHost` (StateV2 / Component) 在 `__init__` 时扫描类注解, 为每个 `sc.Property[...]` 注解的字段创建实例自己的 Property, 因此 `__init__` 里不必再写一遍 (仍可写, 后写的会覆盖). 只认 `Property` / `Property[T]`, 普通注解 (如 `current_scope: str`) 不参与; 类体内的同名值作为默认值 (`age: sc.Property[int] = 0`), 类级别的 `Property` 只贡献它的 default. 子类的 `__init__` 记得调用 `super().__init__()`.
- **值或绑定二选一**: 构造参数用 `p.set_or_bind(x)` 统一处理 -- `x` 是 `Property` 就 `bind` (此后跟随其变化), 否则 `set`. `sc.bind(source, transform)` 用于创建匿名绑定 Property, 例如 `v3.Button('Go', enabled=sc.bind(state.busy, lambda x: not x))`.

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

1. `components_v3/widgets.py` -- 定义 class (按字母序插入, 优先复用私有基类); 在 `components_v3/__init__.py` 里导出.
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
