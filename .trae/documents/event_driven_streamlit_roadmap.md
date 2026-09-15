# 事件驱动 Streamlit 框架 — 路线图

> **状态 (更新于 2026-09-14)**: 本文件是 Phase 0 时期的规划稿, 保留作为设计演进的记录.
> **当前实现以 [`AGENTS.md`](../../AGENTS.md) 为准.** 截至目前 Phase 1–3 已全部落地,
> Phase 4 (与原版 Streamlit 的 UI 细节对齐) 进行中, Phase 5 (迁移与清理) 待办.
> 下文与现状冲突之处已就地更正 (尤其 §2 的"缺口"清单、§4 的阶段状态、§6 的
> `on_change` 传参决策).

## 1. 总结 (Summary)

本项目将从「Streamlit 库的封装扩展」演进为「基于事件系统驱动的 Streamlit 风格框架」。核心变化:执行流不再是每次用户交互后重跑完整脚本,而是仅触发挂载到变化信号上的处理器,并按需 patch 受影响的组件。

按用户决策,采用**混合方案**:
- 先用纯 Python 实现事件驱动内核 (Property / Signal / StateV2 / 组件树),不依赖 Qt,验证概念代码可行性;
- 前端对接 (复用 Streamlit React 还是自建) 推迟到内核稳定后再决定。

Property/Signal 系统在 streamlit_canary 内部重写一份纯 Python 版本,不依赖 qmlease/PySide6。qmlease 的 `qtcore/` 作为参考实现 (现位于 `references/qmlease/`)。

> **现状**: 两项决策均已落地 -- 内核 (`streamlit_canary/kernel/`) 已完成; 前端选择了
> "自建最小前端 + WebSocket" 路线 (`streamlit_canary/runtime/static/`), 不复用
> Streamlit React. 当初的 `lib/qmlease/` 路径已不存在, 参考代码现挂在
> `references/qmlease/qtcore/` (`property.py` / `signal.py` / `qobject.py`)。

## 2. 当前状态分析 (Current State)

### 已有但分散/未成熟的基础设施

> 下表记录的是 Phase 0 时点的状态 (其中多数已被后续实现取代或补齐), 保留以说明设计动机。

| 模块 | 现状 (Phase 0 时点) | 与目标的关系 / 后续结果 |
|---|---|---|
| `streamlit_canary/runner.py` | `sc.run` 通过 `streamlit run` 启动子进程 | 已实现: `sc.run(func, port=...)` 走事件驱动运行时; 传脚本路径时仍回退到这个子进程启动器 |
| `streamlit_canary/session.py` (`SessionStateV2` / `init_state_v2`) | 已有 version/revision 控制、setter 同步 | 该模块仍是 v1 遗留 (绑定 `st.session_state`); 事件驱动的状态容器后来独立实现为 `streamlit_canary/kernel/state.py: StateV2` |
| `streamlit_canary/event_loop.py` | 简单事件队列 + register/run | 思路对,但太简陋,无组件级路由 |
| `streamlit_canary/event_handler_no_rerun.py` | `EventDispatcher`/`EventKey` 走 `st.session_state` | 试图解决 no-rerun,但仍是 Streamlit rerun 的补丁 |
| `streamlit_canary/flow.py` (`PostEvents`) | `append/execute` 回调队列 | 与 event_loop 重复,需统一 |
| `streamlit_canary/compositor.py` | (待确认具体行为) | 与上述三者有重叠,需澄清 |
| `streamlit_canary/components_v2/wrappers.py` | `SelectBox`/`TextInput` 用 `SessionDataV2` 绑定 | v2 组件雏形,但仍依赖 Streamlit 重跑 |
| `streamlit_canary/components_v2/binding.py` | `Binding.trigger` 双向同步 | 组件间值传播的起点 |
| `streamlit_canary/components/button.py`/`container.py`/`text.py` | v1 命令式组件 | 目标是 context-manager + 信号风格 |
| `references/qmlease/qtcore/property.py`/`signal.py`/`qobject.py` | 成熟的 Qt Property/Signal 系统,`DynamicPropMeta` 自动派生 getter/setter/notify | 作为纯 Python 重写的**参考实现**,不直接 import (当时挂在 `lib/qmlease/`) |

### 概念代码目标 API

> 最初指向 `test/event_driven_structure.md`; 该概念稿后来落在
> `test/event_driven_structure/readme.md`, 可运行版本见
> `test/event_driven_structure/demo_click_counter.py`。

```python
class _State(sc.StateV2):
    count = sc.Property(0)           # 派生 6 方法: get/set/on_change/__getitem__/__setitem__/on_<name>
    __version__ = 0                  # 或 __init__(version=...)

state = _State()

def click_counter_demo():
    with sc.v3.Row():
        with sc.v3.Text('Click count: 0') as txt:
            @state.count.on_change.partial(sc._self)   # 更正: on_change 不默认传参
            def _(cnt: sc.Property):
                txt.text.set('Click count: {}'.format(cnt.get()))
        with sc.v3.Button('Increase counter', type='primary') as btn:
            @btn.on_click
            def _():
                state['count'] += 1

sc.run(click_counter_demo, port=3001)   # 直接收函数,不通过 streamlit run 子进程
```

### 关键缺口 (Gaps) — 均已解决

> 下列缺口在 Phase 1–3 中全部落地; 与原计划唯一的偏差是第 4 条: `on_change`
> **不**默认把 Property 句柄传给 handler, 而是用 `Signal.partial(sc._self)` 按需注入
> (见 §6 决策 6)。

1. `sc.StateV2` 基类 — 已实现 (`streamlit_canary/kernel/state.py`)
2. `sc.Property` 纯 Python 版 — 已实现 (`streamlit_canary/kernel/property.py`)
3. `sc.Signal` 纯 Python 版 — 已实现 (`streamlit_canary/kernel/signal.py`)
4. `on_change` 的传参方式 — 最终实现: `Signal.emit()` 不传参; 需要 owner 时用 `.partial(sc._self)` / `.partial(sc._value)`
5. Property 派生 6 方法的具体命名 — 已按概念代码的命名实现
6. `sc.v3.*` context-manager 组件 — 已实现 (清单见 `AGENTS.md` §3)
7. `@btn.on_click` 装饰器模式 — 已实现
8. `txt.text.set(...)` 更新组件属性并触发 UI 刷新 — 已实现 (组件属性复用 `Property` 模型)
9. `sc.run(func, port=...)` 新入口 — 已实现 (函数与脚本两种入口统一在 `sc.run` 中)
10. **No-rerun 运行时** — 已实现 (`streamlit_canary/runtime/`)
11. **前端 delta 协议** — 已实现 (`{"type":"patch","id":...,"prop":...,"value":...}`)

## 3. 涉及的开发工作面 (Development Work Areas)

| # | 工作面 | 职责 | 依赖 |
|---|---|---|---|
| A | **Property/Signal 内核** | 纯 Python 的 `Property` 描述符、`Signal` 类、`partial`; 描述符 `__get__` 返回绑定句柄 + `__init_subclass__` 缓存属性表 (不用元类) | 无 (起点) |
| B | **StateV2 基类** | 继承 Property/Signal,加 version/revision 控制、跨"帧"持久化、与 `sc.init_state` 衔接 | A |
| C | **组件模型 v3** | context-manager 组件 (`Button`/`Text`/`Row`...),持久身份、信号 (`on_click`/`on_change`)、组件属性复用 `Property` 模型 (`txt.text.set(...)`) | A, B |
| D | **组件树 & 生命周期** | 跨交互保持组件树;父-子关系;挂载/卸载;组件 id 生成 | C |
| E | **事件运行时 (核心)** | App 函数仅调用一次构建图;事件队列;信号→处理器路由;仅重跑受影响处理器;状态持久化 | A, B, C, D |
| F | **入口 `sc.run(func, port=...)`** | 新启动器,不走 `streamlit run` 子进程;启动运行时 + (可选) HTTP/WS server | E |
| G | **前端协议 (delta)** | 组件级 patch 协议;widget 事件 → 后端处理器路由 | E (后续阶段) |
| H | **Streamlit 兼容层 (可选)** | 若复用 Streamlit React: 桥接 delta;若自建: 需新前端 | G |
| I | **迁移 & 清理** | 把 v1/v2 组件 (tree_select/filelist/...) 迁到 v3;删除 `event_loop.py`/`flow.py`/`event_handler_no_rerun.py`/`compositor.py` 中的重复实现 | E 稳定后 |

## 4. 路线图 (Phased Roadmap)

### Phase 0 — 概念演示 ✅

**产出**: 概念稿落在 `test/event_driven_structure/readme.md`, 可运行版本为
`test/event_driven_structure/demo_click_counter.py` (概念稿已随之更新为当前 API)。

**目的**: 把目标 API 钉死,作为后续所有阶段的契约。当时 Property/Signal/StateV2
尚不存在,这份文件作为"目标快照"指导 Phase 1 设计。

**范围**:
- 展示 `sc.StateV2` + `sc.Property` 的 6 方法派生
- 展示 `sc.v3.Row`/`sc.v3.Text`/`sc.v3.Button` context-manager + 信号
- 展示 `@state.count.on_change` 注册 handler (最终实现需 `.partial(sc._self)` 注入 owner)
- 展示 `@btn.on_click` 装饰器
- 展示 `txt.text.set(...)` 属性更新 (组件属性复用 Property 模型)
- 展示 `sc.run(func, port=...)` 新入口

### Phase 1 — Property/Signal 内核 ✅

**产出**: 纯 Python 的 Property/Signal/StateV2,可在隔离脚本中验证 (不接 Streamlit)。
已落在 `streamlit_canary/kernel/` (`property.py` / `signal.py` / `special_value.py` / `state.py`)。

**关键设计点**:
- `Property` 描述符: 类属性形式声明,实例化时创建 getter/setter/signal
- 不用 metaclass,改用 `__init_subclass__` 扫描并缓存属性列表 + 描述符 `__get__` 返回绑定句柄
- `__getitem__`/`__setitem__`: `state['count']` 走 `get()`/`set()`
- `state['on_count']` / `state.count.on_change`: 都指向同一个 `Signal` 实例
- `Property.set()` 触发 `on_change.emit()` **不默认传参**; 需要 owner / value 时用
  `Signal.partial(sc._self)` / `Signal.partial(sc._value)` 按需注入
- `Signal.partial` 作为通用静态参数绑定 (无 `'self'` 魔法,特殊标记见 `special_value.py`)
- `__version__` / `version=` kwarg: 控制 schema 变更时是否重建 state

**参考实现**: 当初参考了 qmlease 的 `qtcore/property.py`、`qobject.py`
(`DynamicPropMeta`); 参考代码现位于 `references/qmlease/`, 而 `streamlit_canary/kernel/`
的实现已完全独立为纯 Python, 不 import 它。

**验证**: `python test/on_property_test.py` (不依赖 Streamlit, 验证 Property/Signal 的
6 方法、`partial(sc._self)` / `partial(sc._value)` 注入、version 行为)。

### Phase 2 — 组件模型 v3 ✅

**产出**: `sc.v3.*` context-manager 组件,挂在运行时之前的纯 Python 层
(放在 `sc.v3.*` 下避免污染稳定命名空间)。已落在 `streamlit_canary/components_v3/`
(`base.py` + `widgets.py`), 组件清单见 `AGENTS.md` §3。

**关键设计点**:
- `with sc.v3.Button(...) as btn:` 构造组件,返回带持久 id 的实例
- `btn.on_click` 是 `Signal`,支持 `@btn.on_click` 装饰器注册处理器
- 组件视觉属性复用 `Property` 模型:`txt.text.set(...)` 发出 `txt.text.on_change`
  信号 → 通知运行时;与 state 读写风格统一
- 组件树通过 `with` 嵌套建立父子关系 (基于 `Component._context_stack`)
- 公共字段抽象为私有基类 (`_HasText` / `_Labeled` / `_OptionsWidget` / `_TextVisible`)
  以复用,详见 `AGENTS.md` §8

**验证**: `python test/event_driven_structure/components_v3_demo.py`,纯 Python 构造
组件树,手动触发信号,断言属性变化和处理器调用。

### Phase 3 — 事件运行时 (核心) ✅

**产出**: `sc.run(func, port=...)` 启动事件运行时,app 函数只跑一次,后续用户交互仅触发对应信号处理器;含 Starlette+Uvicorn Web 服务 + WebSocket delta 推送 + 最小前端。

**关键设计点**:
- 运行时维护: 组件树 (持久) + state (持久) + 信号→处理器映射
- `Runtime.build()` 设置 `Component._active_runtime`,app 函数执行时组件自动注册到运行时
- 调度: 收到客户端事件 → 找到对应 signal → 调用所有挂载的 handler → handler 修改 Property → Property 发出 on_change → runtime 推送 delta 到所有 WS 客户端
- delta 协议: `{"type":"patch","id":"<comp-id>","prop":"text","value":"..."}`;事件: `{"type":"event","id":"<comp-id>","event":"click"}`
- 前端: 组件渲染为带 `data-id` 的 DOM 元素,WS 收到 patch 时按 id 更新 `textContent`

**验证**: `python test/event_driven_structure/demo_click_counter.py`,浏览器打开点击按钮,计数器递增且无页面刷新。

### Phase 4 — 前端协议决策 & 对接 (进行中)

**决策结果**: 选择了 **方案 B (自建最小前端 + WebSocket, 自己定义组件级 delta
协议)**, 不复用 Streamlit React。前端资源独立存放在
`streamlit_canary/runtime/static/` (`page.css` / `page.js` / `theme-*.css`), 由运行时
在模块导入时加载。

**当前进度**: 基础渲染 + delta 推送已可用; 本阶段剩余工作是**与原版 Streamlit 的
UI 细节对齐** (以 `test/event_driven_structure/pyproject_manager_copy/` 对照
`references/pyproject_manager/`, 见 `AGENTS.md` §4/§5)。

**产出**: 选定方案并实现最小可点击 demo (浏览器打开能看到 counter) — 已完成, 并在
其之上持续扩展组件 (Code / Popover / Checkbox / Radio horizontal 等)。

### Phase 5 — 迁移与清理 (待办)

- 把 v1/v2 现有组件 (tree_select、filelist、progress、card、radio、toggle...) 迁到 v3 模型
- 删除 `event_loop.py`、`flow.py`、`event_handler_no_rerun.py`、`compositor.py` 中已被运行时取代的重复实现
- 更新 `changelog.md` 标记 0.4.0 "Native execution flow" 完成

## 5. 起点 (Where to Start)

> 本节是 Phase 0 时点的启动计划, 现已全部执行完毕, 保留以说明当初的切入顺序。

**第一阶段实施 (Phase 1)**: 在 `streamlit_canary/` 下新建 `kernel/` 模块,实现纯 Python
的 `Property`/`Signal`/`StateV2`,并用 `test/on_property_test.py` 验证 6 方法 +
`partial` 注入 + version 控制。

**为什么从内核开始**:
- 概念代码的所有其他部分 (组件、运行时、入口) 都建立在 Property/Signal 之上
- 内核可以独立验证,不需要 Streamlit、不需要前端,反馈循环最短
- 现有 `SessionStateV2` 已经验证了 version 控制的价值,可以直接借鉴
- qmlease 提供了成熟参考实现,重写风险可控

## 6. 假设与决策 (Assumptions & Decisions)

1. **Property/Signal 在 sc 内重写** (不依赖 qmlease/PySide6) — 用户确认
2. **混合方案**: 先纯 Python 内核,前端对接延后 — 用户确认
3. **路线图粒度**: 高层,不细化到文件级 — 用户确认;Phase 1 的文件级细化留待 Phase 0 完成后另起一轮计划
4. **`sc.run` 语义统一** (Phase 3 最终决定): `sc.run(func, port=...)` 直接收应用函数, 走事件驱动运行时; 传入脚本路径时回退到 `streamlit run` 子进程启动器 (`streamlit_canary/runner.py`)。不再引入 `sc.run_event_driven` 之类的新名字
5. **Phase 4 前端决策** (**已决定**): 选择方案 B — 自建最小前端 (`runtime/static/`) + 自定义组件级 delta 协议, 不复用 Streamlit React
6. **`on_change` 传参语义** (**最终实现**): `Property.set()` 触发 `on_change.emit()`, **不默认传参**。需要拿到 owner 或新值时, 用特殊标记按需注入:
   - `@prop.on_change.partial(sc._self)` → handler 收到触发变更的 Property handle
   - `@prop.on_change.partial(sc._value)` → handler 收到 `owner.get()`
   - 普通值 `@prop.on_change.partial('x')` → 原样绑定为第一个参数
   `Signal.partial` 仍作为通用静态参数绑定保留; 特殊标记定义见 `kernel/special_value.py`

## 7. 验证步骤 (Verification)

| Phase | 验证方式 |
|---|---|
| 0 | 代码评审: `test/event_driven_structure/readme.md` + `demo_click_counter.py` 展示概念代码所有特性 |
| 1 | `python test/on_property_test.py` 跑通,断言 6 方法、`partial` 注入、version 行为 |
| 2 | `python test/event_driven_structure/components_v3_demo.py` 构造组件树,模拟 click,断言处理器被调用 |
| 3 | `python test/event_driven_structure/demo_click_counter.py` 启动 counter,断言 app 函数只执行一次,counter 正确递增 |
| 4 | 浏览器打开 `localhost:<port>`,点击按钮,看到 counter 更新;多次点击验证无全量重跑;并在 `:3001` vs `:2130` 对照采集 UI 细节 |
| 5 | 现有 v1/v2 组件在新模型下可用;旧重复模块删除后 `python test/` 全部通过 |
