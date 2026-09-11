# AGENTS.md

> 对 AI agent 的项目指引. 每当 agent 进入此仓库工作时, 请先阅读本文档.

## 1. 项目概况

**Streamlit Canary** (`streamlit-canary`) 是对 Streamlit 的二次开发, 扩展了原版的组件库, 并实现了一套基于事件驱动的运行时. 开发者用纯 Python 写组件树, 运行时负责渲染 HTML, 路由事件, 推送 delta patch, 前端局部更新 DOM, 无需页面刷新.

- **语言**: Python 3.12 及以上
- **版本**: 0.4.0a9
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
│   │   ├── signal.py         # Signal: 事件信号
│   │   └── state.py          # StateV2: 状态容器
│   ├── components_v3/        # v3 事件驱动组件
│   │   ├── base.py           # Component 基类: 注册到 runtime, 属性绑定
│   │   └── widgets.py        # 具体组件实现
│   ├── runtime/              # 事件驱动运行时
│   ├── components/           # v1 组件 (基于 Streamlit)
│   ├── components_v2/        # v2 组件 (过渡版本)
│   ├── session.py            # Session state 管理
│   └── runner.py             # 传统 Streamlit 子进程启动器 (legacy)
├── test/                     # 测试与演示
│   ├── event_driven_structure/     # v3 事件驱动测试
│   │   ├── demo_click_counter.py   # 计数器 demo
│   │   └── pyproject_manager_copy/ # pyproject-manager 的 v3 重写版 (运行在 localhost:3001)
│   └── ...
├── references/               # 参考资源
│   ├── pyproject_manager/    # 原版基于 Streamlit 的演示应用, 运行在 localhost:2130
│   ├── streamlit/            # Streamlit 源码
│   └── ...                   # 截图, 参考图等
├── pyproject.toml            # 项目配置
└── changelog.md              # 变更记录
```

## 3. 开发进度

### 已完成

- **Phase 1**: Kernel 层(Property, Signal, StateV2)
- **Phase 2**: Components v3 层(Row, Column, Text, Title, Button, Selectbox, Radio)
- **Phase 3**: 事件驱动运行时(Runtime, Server, Render)
- **Phase 4 (进行中)**: 前端协议与 UI 细节对齐

### 待办

- [ ] 更多组件迁移(Phase 5)
- [ ] 前端协议完善(Phase 4 继续)
- [ ] 与原版 Streamlit 的更多 UI 细节对齐

## 4. 开发环境

### 常用命令

```bash
# 同步依赖
uv sync

# 运行 v3 测试应用
python test/event_driven_structure/pyproject_manager_copy/app.py    # :3001

# 运行原版 (用于对比)
# 原版 pyproject-manager 运行在 :2130

# 静态检查
ruff check streamlit_canary/
ruff format streamlit_canary/
ty check streamlit_canary/

# 运行内核测试
python test/event_driven_structure/state_kernel_demo.py
python test/event_driven_structure/components_v3_demo.py
```

### 对比测试环境

- **原版**: `http://localhost:2130` (references/pyproject_manager, 基于 Streamlit)
- **我们的**: `http://localhost:3001` (test/event_driven_structure/pyproject_manager_copy, 基于 v3 运行时)

UI 细节对齐时, 通常需要在两个端口分别采集数据, 逐一对比.

## 5. 伪代码驱动的 UI 验证方法

在与 agent 交流 UI 交互和视觉要求时, **纯文字描述往往不够精确**. 推荐使用 **伪代码 (pseudo-code)** 来描述交互操作和断言.

### 5.1 为什么用伪代码

- 文字描述容易遗漏细节 (如 "hover 时背景应该是灰色" -- 哪个元素的灰色? 和谁对齐?)
- 伪代码可以精确表达:
  - **操作序列**: 先做什么, 再做什么
  - **目标元素**: 通过属性或层级定位
  - **断言条件**: 具体的 CSS 属性值, 几何关系
- Agent 可以直接把伪代码翻译为浏览器自动化行为

### 5.2 伪代码示例

伪代码不需要可执行, 但需要描述测试意图和可被自动化实现的操作步骤:

```
# 1. 打开应用, 定位元素
sc_app = open_browser(localhost:3001)
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

### 5.3 Agent 工作流

当用户提供伪代码时, agent 应该:

1. **解析伪代码**: 识别操作序列, 目标元素, 断言条件
2. **采集数据**: 用 `browser_evaluate` 在原版 (`:2130`) 和我们的 (`:3001`) 分别采集断言处的实际值
3. **对比分析**: 找出差异
4. **修复代码**: 修改 `render.py` (HTML 结构 / CSS / JS) 或 `widgets.py` (组件定义)
5. **重新验证**: 重启服务, 再次采集数据, 确认所有 assert 通过

## 6. 工具链

- 使用 `python ...` 运行脚本 (已配置 `PYTHONPATH`,不需要 `sys.path.append`).
- 使用 `uv sync` 同步依赖, 使用 `uv` 管理 `pyproject.toml` 中的依赖.
- 使用 `ty check` 检查类型错误.
- 使用 `ruff check` 检查代码风格, 使用 `ruff format` 格式化代码.
- 每当完成修改后, 运行 `ty check`、`ruff check`、`ruff format` 确认无误.

## 7. 代码风格

- 优先使用 `format` 而不是 `f-string`.
- 代码中使用全英文注释, 不要有中文注释.
- 不需要在入口脚本的顶部添加 `sys.path.append(...)`. 因为我们已经设置好了环境变量 (`PYTHONPATH=.;src;lib;.venv/Lib/site-packages`).
- 每行代码不超过 80 字符 (见 `pyproject.toml:[tool.ruff]:line-length`).
- import 使用 force-single-line 风格 (见 `pyproject.toml:[tool.ruff.lint.isort]`).
- 字符串使用单引号 (见 `pyproject.toml:[tool.ruff.format]:quote-style`).

## 8. 架构约束

- **State 和 Components 统一读写风格**: `.get()` / `.set()` / `on_change` / `__set__` / `__setitem__`, 降低理解负担.
- **组件属性**: 可响应字段用 `Property` (如 `Text.text`, `Selectbox.value`), 静态配置用 `_` 前缀属性(如 `Button._type`, `Button._width`).
- **不使用 metaclass**: 因为 metaclass 会增加理解负担, 而且在当前实现中, 它的使用是不透明的.
- **v2/v3 命名空间**: v2/v3 的新元素不直接暴露在 `__init__.py`, 用 `components_v3` 作为 v3 命名空间 (如 `sc.v3.Button`).
- **Web 服务**: 用 Starlette + Uvicorn (HTTP 页面 + WebSocket 事件/delta), 不用 FastAPI.
- **Web 服务器非阻塞**: 必须非阻塞启动, 可用 StopCommand 停止.
- **Python 3.12**: 使用现代语法 (`type | type` 联合, `match` 等).
