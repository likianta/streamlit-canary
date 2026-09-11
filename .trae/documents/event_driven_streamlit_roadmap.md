# 事件驱动 Streamlit 框架 — 路线图

## 1. 总结 (Summary)

本项目将从「Streamlit 库的封装扩展」演进为「基于事件系统驱动的 Streamlit 风格框架」。核心变化:执行流不再是每次用户交互后重跑完整脚本,而是仅触发挂载到变化信号上的处理器,并按需 patch 受影响的组件。

按用户决策,采用**混合方案**:
- 先用纯 Python 实现事件驱动内核 (Property / Signal / StateV2 / 组件树),不依赖 Qt,验证概念代码可行性;
- 前端对接 (复用 Streamlit React 还是自建) 推迟到内核稳定后再决定。

Property/Signal 系统在 streamlit_canary 内部重写一份纯 Python 版本,不依赖 qmlease/PySide6。现有的 `lib/qmlease/qtcore/` 作为参考实现。

## 2. 当前状态分析 (Current State)

### 已有但分散/未成熟的基础设施

| 模块 | 现状 | 与目标的关系 |
|---|---|---|
| `streamlit_canary/runner.py` | `sc.run` 通过 `streamlit run` 启动子进程 | 目标要改为 `sc.run(func, port=...)` 直接收函数,不通过子进程 |
| `streamlit_canary/session.py` (`SessionStateV2` / `init_state_v2`) | 已有 version/revision 控制、setter 同步 | 是 StateV2 的雏形,但绑定 `st.session_state`,无信号传播 |
| `streamlit_canary/event_loop.py` | 简单事件队列 + register/run | 思路对,但太简陋,无组件级路由 |
| `streamlit_canary/event_handler_no_rerun.py` | `EventDispatcher`/`EventKey` 走 `st.session_state` | 试图解决 no-rerun,但仍是 Streamlit rerun 的补丁 |
| `streamlit_canary/flow.py` (`PostEvents`) | `append/execute` 回调队列 | 与 event_loop 重复,需统一 |
| `streamlit_canary/compositor.py` | (待确认具体行为) | 与上述三者有重叠,需澄清 |
| `streamlit_canary/components_v2/wrappers.py` | `SelectBox`/`TextInput` 用 `SessionDataV2` 绑定 | v2 组件雏形,但仍依赖 Streamlit 重跑 |
| `streamlit_canary/components_v2/binding.py` | `Binding.trigger` 双向同步 | 组件间值传播的起点 |
| `streamlit_canary/components/button.py`/`container.py`/`text.py` | v1 命令式组件 | 目标是 context-manager + 信号风格 |
| `lib/qmlease/qtcore/property.py`/`signal.py`/`qobject.py` | 成熟的 Qt Property/Signal 系统,`DynamicPropMeta` 自动派生 getter/setter/notify | 作为纯 Python 重写的**参考实现**,不直接 import |

### 概念代码目标 API ([test/event_driven_structure.md](file:///c:/Likianta/workspace/dev.master.likianta/streamlit-canary/test/event_driven_structure.md))

```python
class _State(sc.StateV2):
    count = sc.Property(0)           # 派生 6 方法: get/set/on_change/__getitem__/__setitem__/on_<name>
    __version__ = 0                  # 或 __init__(version=...)

state = _State()

def click_counter_demo():
    with sc.v3.Row():
        with sc.v3.Text('Click count: 0') as txt:
            @state.count.on_change
            def _(cnt: sc.Property):
                txt.text.set('Click count: {}'.format(cnt.get()))
        with sc.v3.Button('Increase counter', type='primary') as btn:
            @btn.on_click
            def _():
                state['count'] += 1

sc.run(click_counter_demo, port=3001)   # 直接收函数,不通过 streamlit run 子进程
```

### 关键缺口 (Gaps)

1. `sc.StateV2` 基类 — 不存在
2. `sc.Property` 纯 Python 版 — 不存在 (仅 qmlease 有 Qt 版)
3. `sc.Signal` 纯 Python 版 — 不存在
4. `Property.on_change` emit 时直接传出 Property 句柄本身,handler 通过 `cnt.get()` 读取新值 — 需明确设计
5. Property 派生 6 方法的具体命名 (`state.count.get()` / `state.count.on_change` / `state['on_count']`) — qmlease 命名是 `get_*`/`set_*`/`*_changed`,需在 sc 版本中按概念代码的命名重写
6. `sc.v3.Row`/`sc.v3.Text`/`sc.v3.Button` context-manager 组件 — 部分存在 (v1),但无信号、无持久身份;v3 组件放在 `sc.v3.*` 下避免污染稳定命名空间
7. `@btn.on_click` 装饰器模式 — 不存在
8. `txt.text.set(...)` 更新组件属性并触发 UI 刷新 — 组件属性复用 `Property` 模型,与 state 读写风格统一
9. `sc.run(func, port=...)` 新入口 — 不存在 (现有 `sc.run` 走子进程)
10. **No-rerun 运行时** — 不存在,需从零构建 (组件树持久化 + 事件路由 + 仅触发受影响处理器)
11. **前端 delta 协议** — 未决定 (留待 Phase 4)

## 3. 涉及的开发工作面 (Development Work Areas)

| # | 工作面 | 职责 | 依赖 |
|---|---|---|---|
| A | **Property/Signal 内核** | 纯 Python 的 `Property` 描述符、`Signal` 类、`partial`、元类自动派生 6 方法 | 无 (起点) |
| B | **StateV2 基类** | 继承 Property/Signal,加 version/revision 控制、跨"帧"持久化、与 `sc.init_state` 衔接 | A |
| C | **组件模型 v3** | context-manager 组件 (`Button`/`Text`/`Row`...),持久身份、信号 (`on_click`/`on_change`)、组件属性复用 `Property` 模型 (`txt.text.set(...)`) | A, B |
| D | **组件树 & 生命周期** | 跨交互保持组件树;父-子关系;挂载/卸载;组件 id 生成 | C |
| E | **事件运行时 (核心)** | App 函数仅调用一次构建图;事件队列;信号→处理器路由;仅重跑受影响处理器;状态持久化 | A, B, C, D |
| F | **入口 `sc.run(func, port=...)`** | 新启动器,不走 `streamlit run` 子进程;启动运行时 + (可选) HTTP/WS server | E |
| G | **前端协议 (delta)** | 组件级 patch 协议;widget 事件 → 后端处理器路由 | E (后续阶段) |
| H | **Streamlit 兼容层 (可选)** | 若复用 Streamlit React: 桥接 delta;若自建: 需新前端 | G |
| I | **迁移 & 清理** | 把 v1/v2 组件 (tree_select/filelist/...) 迁到 v3;删除 `event_loop.py`/`flow.py`/`event_handler_no_rerun.py`/`compositor.py` 中的重复实现 | E 稳定后 |

## 4. 路线图 (Phased Roadmap)

### Phase 0 — 概念演示 (立即, 本次讨论后)

**产出**: `./test/demo_click_counter.py` — 基于 `./test/event_driven_structure.md` 优化的"暂时跑不通但清晰展示新特性"的演示代码。

**目的**: 把目标 API 钉死,作为后续所有阶段的契约。即使 Property/Signal/StateV2 还不存在,这份文件作为"目标快照"指导 Phase 1 设计。

**范围**:
- 展示 `sc.StateV2` + `sc.Property` 的 6 方法派生
- 展示 `sc.v3.Row`/`sc.v3.Text`/`sc.v3.Button` context-manager + 信号
- 展示 `@state.count.on_change` 注册 handler,handler 直接接收 Property 句柄
- 展示 `@btn.on_click` 装饰器
- 展示 `txt.text.set(...)` 属性更新 (组件属性复用 Property 模型)
- 展示 `sc.run(func, port=...)` 新入口
- 文件头加注释说明"该演示依赖未实现的 v3 API,运行会失败"

### Phase 1 — Property/Signal 内核 (起点)

**产出**: 纯 Python 的 Property/Signal/StateV2,可在隔离脚本中验证 (不接 Streamlit)。

**关键设计点**:
- `Property` 描述符: 类属性形式声明,实例化时创建 getter/setter/signal
- 不用 metaclass,改用 `__init_subclass__` 扫描并缓存属性列表 + 描述符 `__get__` 返回绑定句柄
- `__getitem__`/`__setitem__`: `state['count']` 走 `get()`/`set()`
- `state['on_count']` / `state.count.on_change`: 都指向同一个 `Signal` 实例
- `Property.set()` 触发 `on_change.emit(self)`,把 Property 句柄自身作为参数传出;handler 直接 `cnt.get()` 读值
- `Signal.partial` 保留为通用静态参数绑定 (无 `'self'` 魔法)
- `__version__` / `version=` kwarg: 控制 schema 变更时是否重建 state

**参考实现**: `lib/qmlease/qtcore/property.py`、`qobject.py` 的 `DynamicPropMeta`,但全部重写为纯 Python。

**验证**: 写一个 `test/state_kernel_demo.py`,不依赖 Streamlit,只验证 Property/Signal 的 6 方法、on_change 传句柄、version 行为正确。

### Phase 2 — 组件模型 v3

**产出**: `sc.v3.Row`/`sc.v3.Text`/`sc.v3.Button` 等 context-manager 组件,挂在运行时之前的纯 Python 层 (放在 `sc.v3.*` 下避免污染稳定命名空间)。

**关键设计点**:
- `with sc.v3.Button(...) as btn:` 构造组件,返回带持久 id 的实例
- `btn.on_click` 是 `Signal`,支持 `@btn.on_click` 装饰器注册处理器
- 组件视觉属性复用 `Property` 模型:`txt.text.set(...)` 发出 `txt.text.on_change` 信号 → 通知运行时;与 state 读写风格统一
- 组件树通过 `with` 嵌套建立父子关系
- 组件 id 生成 (参考 `streamlit_canary/keygen.py`)

**验证**: `test/components_v3_demo.py`,纯 Python 构造组件树,手动触发信号,断言属性变化和处理器调用。

### Phase 3 — 事件运行时 (核心) ✅

**产出**: `sc.run(func, port=...)` 启动事件运行时,app 函数只跑一次,后续用户交互仅触发对应信号处理器;含 Starlette+Uvicorn Web 服务 + WebSocket delta 推送 + 最小前端。

**关键设计点**:
- 运行时维护: 组件树 (持久) + state (持久) + 信号→处理器映射
- `Runtime.build()` 设置 `Component._active_runtime`,app 函数执行时组件自动注册到运行时
- 调度: 收到客户端事件 → 找到对应 signal → 调用所有挂载的 handler → handler 修改 Property → Property 发出 on_change → runtime 推送 delta 到所有 WS 客户端
- delta 协议: `{"type":"patch","id":"<comp-id>","prop":"text","value":"..."}`;事件: `{"type":"event","id":"<comp-id>","event":"click"}`
- 前端: 组件渲染为带 `data-id` 的 DOM 元素,WS 收到 patch 时按 id 更新 `textContent`

**验证**: `python test/demo_click_counter.py`,浏览器打开点击按钮,计数器递增且无页面刷新。

### Phase 4 — 前端协议决策 & 对接

**决策点**: 此时内核已稳定,要决定
- **方案 A**: 复用 Streamlit React + websocket,把运行时的"脏组件"diff 成 Streamlit delta 协议发出去
- **方案 B**: 自建最小前端 + websocket,自己定义组件级 delta 协议

**产出**: 选定方案并实现最小可点击 demo (浏览器打开能看到 counter)。

### Phase 5 — 迁移与清理

- 把 v1/v2 现有组件 (tree_select、filelist、progress、card、radio、toggle...) 迁到 v3 模型
- 删除 `event_loop.py`、`flow.py`、`event_handler_no_rerun.py`、`compositor.py` 中已被运行时取代的重复实现
- 更新 `changelog.md` 标记 0.4.0 "Native execution flow" 完成

## 5. 起点 (Where to Start)

**立即动作 (Phase 0)**: 创建 `./test/demo_click_counter.py`,作为目标 API 契约。

**第一阶段实施 (Phase 1)**: 在 `streamlit_canary/` 下新建 `kernel/` 模块,实现纯 Python 的 `Property`/`Signal`/`StateV2`,并用 `test/state_kernel_demo.py` 验证 6 方法 + on_change 传句柄 + version 控制。

**为什么从内核开始**:
- 概念代码的所有其他部分 (组件、运行时、入口) 都建立在 Property/Signal 之上
- 内核可以独立验证,不需要 Streamlit、不需要前端,反馈循环最短
- 现有 `SessionStateV2` 已经验证了 version 控制的价值,可以直接借鉴
- qmlease 提供了成熟参考实现,重写风险可控

## 6. 假设与决策 (Assumptions & Decisions)

1. **Property/Signal 在 sc 内重写** (不依赖 qmlease/PySide6) — 用户确认
2. **混合方案**: 先纯 Python 内核,前端对接延后 — 用户确认
3. **路线图粒度**: 高层,不细化到文件级 — 用户确认;Phase 1 的文件级细化留待 Phase 0 完成后另起一轮计划
4. **现有 `sc.run` 语义保留兼容**: 新 `sc.run(func, port=...)` 与旧 `sc.run(...)` (走 streamlit 子进程) 签名不兼容,旧用法将在 Phase 5 弃用;过渡期可用不同函数名 (如 `sc.run_event_driven`) 区分 — 此细节留待 Phase 3 决定
5. **Phase 4 的前端决策推迟**: 不在现阶段预设方案 A 或 B
6. **`on_change` 传参语义**: `Property.set()` 触发 `on_change.emit(self)`,把发生变化的 Property 句柄自身作为参数传给 handler;handler 直接 `cnt.get()` 读新值。不使用 `partial('self')` 魔法 (已废弃)。`Signal.partial` 仅作为通用静态参数绑定保留

## 7. 验证步骤 (Verification)

| Phase | 验证方式 |
|---|---|
| 0 | 代码评审: demo_click_counter.py 完整展示概念代码所有特性,文件头注释说明不可运行 |
| 1 | `python test/state_kernel_demo.py` 跑通,断言 6 方法、partial、version 行为 |
| 2 | `python test/components_v3_demo.py` 构造组件树,模拟 click,断言处理器被调用 |
| 3 | `python test/runtime_demo.py` 跑 counter 逻辑,断言 app 函数只执行一次,counter 正确递增 |
| 4 | 浏览器打开 `localhost:<port>`,点击按钮,看到 counter 更新;多次点击验证无全量重跑 |
| 5 | 现有 v1/v2 组件在新模型下可用;旧重复模块删除后 `python test/` 全部通过 |
