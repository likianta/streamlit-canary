# 基于事件驱动的 Streamlit (no-reruns)

Streamlit 的性能随着项目复杂度的提升而面临挑战, 特别是对实时性要求较高的场景, 一大原因是由它的 rerun 特性造成的, 但也跟人们无法精细拆分性能关键点有关.

我想试着去掉 rerun, 改为 QtQuick 的 signal-slot 的事件驱动设计, 不过这是一个庞大的工程, 对我个人来说几乎是不可能的, 所以我在前几年产生的这个想法一直非常缓慢地推进, 直到我使用了 AI, 从最近的 GitHub 提交频率来看, 我成功了.

我大概花了一个月时间 (其实大部分工作在第一周就完成了) 实现了这个功能. 你可以在这里访问它的 GitHub 仓库: [streamlit-canary](https://github.com/likianta/streamlit-canary). (文档入口: [用户手册](https://likianta.github.io/streamlit-canary/))

以及两张基于它构建的产品截图:

![](./images/261019-160630.png)

![](./images/261019-160727.png)

## 特性

- 基于性能设计. 入口函数只运行一次, 组件树完整推送到前端, 后续通过 patch 来局部更新运行时组件.
- 响应式设计, 且语法经过精心打磨, 使用起来更方便, 更直接, 更符合直觉.
- 以桌面窗口的形式启动 (Toga WebView). 启动器图标, 窗口标题, 窗口尺寸调节均支持.
- 一套预置的组件库. 除了 Streamlit 的官方组件[^1], 还增加了文件树, PDF Viewer, 实时日志面板, 浮动通知等.
- `dunder_literal`, 通过配置该选项, 可以避免 Markdown 误将 `__init__`, `__name__` 这类名称转换成加粗文本 (`**name**`, `:bold[name]` 仍然支持加粗).
- 更少的依赖. Streamlit Canary 不包含 numpy, pandas, scipy, pyarrow, altair[save] 等依赖.

## 与 Streamlit 对比

### 启动入口

Streamlit Canary:

```python
import streamlit_canary as sc

def setup_ui():
    ...

# streamlit-canary
if __name__ == '__main__':
    # python app.py
    sc.run(setup_ui, port=3001)
```

Streamlit:

```python
import streamlit as st

def setup_ui():
    ...

if __name__ == '__main__':
    # python -m streamlit run --runner.magicEnabled false --server.headless \
    #   true --server.port 3001 app.py 
    setup_ui()
```

### Hello world

Streamlit Canary:

```python
import streamlit_canary as sc

def app():
    sc.PageTitle('Click Counter', default_theme='dark')
    
    cnt = sc.Property(0)
    
    with sc.Row('center'):
        sc.Text(sc.bind(cnt, lambda x: 'Click count: {}'.format(x)))
        #   when `cnt` changes, `sc.bind` emits new text to the Text component.

        with sc.Button('Increase counter', type='primary') as btn:
            @btn.on_click
            def _():
                cnt.set(cnt.get() + 1)

if __name__ == '__main__':
    # python app.py
    sc.run(app, port=3001)
```

Streamlit:

```python
import streamlit as st

def app():
    st.set_page_config('Click Counter')
    st.title('Click Counter')

    with st.container(horizontal_alignment=True, vertical_alignment='center'):
        text_place = st.empty()
        if st.button('Increase counter', type='primary'):
            st.session_state.count += 1
        with text_place:
            st.text('Click count: {}'.format(st.session_state.count))

if __name__ == '__main__':
    # python -m streamlit run \
    #   --runner.magicEnabled false \
    #   --server.headless true \
    #   --server.port 3001 \
    #   --theme.base dark \
    #   app.py
    app()
```

### Session State

Streamlit 用 `st.session_state` 保存跨 rerun 的状态. 脚本每一轮都会重新执行, 所以状态必须放进 `session_state`, 否则下一轮就丢了. 控件通过 `key` 或返回值与状态同步:

```python
import streamlit as st

if 'name' not in st.session_state:
    st.session_state.name = ''

st.text_input('Name', key='name')
st.text('Hello, {}'.format(st.session_state.name or 'stranger'))
```

Streamlit Canary 用 `State` + `Property`. 入口函数只运行一次, 状态是长期存在的响应式对象, 可以 `.get()` / `.set()`, 也可以直接绑定到组件:

```python
import streamlit_canary as sc

class State(sc.State):
    name = sc.Property('')

state = State()

def app():
    sc.TextInput('Name', sc.bbind(state.name))
    sc.Text(
        sc.bind(state.name, lambda x: 'Hello, {}'.format(x or 'stranger'))
    )
```

### 事件响应

Streamlit 的交互最终都会变成一次 rerun. 可以用 `if st.button(...)` 在当前轮判断, 也可以用 `on_click` 回调; 回调会在 rerun 前执行, 但脚本仍然会完整地再跑一遍:

```python
import streamlit as st

if 'count' not in st.session_state:
    st.session_state.count = 0

def increase():
    st.session_state.count += 1

st.button('Increase counter', on_click=increase)
st.text('Click count: {}'.format(st.session_state.count))
```

Streamlit Canary 把事件建模为 `Signal`. 组件暴露 `on_click`, `on_change`, `on_submit` 等信号; 用装饰器注册的 handler 只在该事件发生时执行, 入口函数不会重跑:

```python
import streamlit_canary as sc

class State(sc.State):
    count = sc.Property(0)

state = State()

def app():
    with sc.Text('Click count: 0') as txt:
        @state.count.on_change.partial(sc._self)
        def _(count):
            txt.text.set('Click count: {}'.format(count.get()))

    with sc.Button('Increase counter') as btn:
        @btn.on_click
        def _():
            state['count'] += 1
```

这里的 `state.count.on_change` 和 `btn.on_click` 都是普通的 `Signal` 对象, 可以手动 `emit()`, 也可以被多个 handler 订阅. `sc._self` / `sc._value` 用来在注册时声明"我需要 owner 还是它的当前值".

### 更多对比示例

**布局**. Streamlit 用 `st.columns` / `st.container` / `st.expander` / `st.tabs`; Canary 用对应的 `sc.Row` / `sc.Column` / `sc.Container` / `sc.Expander` / `sc.Tabs`. 组件树只构建一次, 之后改属性即可:

```python
# Streamlit
left, right = st.columns(2)
with left:
    st.write('Left')
with right:
    st.write('Right')
```

```python
# Streamlit Canary
with sc.Row():
    with sc.Column(weight=1):
        sc.Text('Left')
    with sc.Column(weight=1):
        sc.Text('Right')
```

**条件显示**. Streamlit 里通常写成 `if` 分支; Canary 里组件先创建, 再用`visible` 控制显示:

```python
# Streamlit
if st.toggle('Advanced'):
    st.text_input('Extra option')
```

```python
# Streamlit Canary
advanced = sc.Toggle('Advanced')
with sc.Container(visible=advanced.value, animated=True):
    sc.TextInput('Extra option')
```

**自研组件**. 除了 Streamlit 风格的组件, Canary 还内置了文件树, PDF Viewer, 实时日志面板, 浮动通知等:

```python
sc.PathInputBrowse('Project folder', '.')
sc.PdfViewer('manual.pdf')
sc.LogPanel(source='stdout')
sc.toast('Saved!', icon=':material/check:')
```

**桌面窗口**. `sc.run(..., show_window=True)` 可以直接把应用开在原生窗口里, 不需要浏览器:

```python
sc.run(app, show_window=True, window_size=(980, 760))
```

需要说明的是, Streamlit 的生态更成熟, 组件覆盖更全; Canary 目前仍在 v0.4.x, 部分官方组件 (例如图表) 还在补齐.

## 安装

```bash
pip install streamlit-canary
```

要求 Python 3.11 及以上版本.

## 快速开始

```python
import streamlit_canary as sc

class State(sc.State):
    count = sc.Property(0)

state = State()

def app():
    sc.PageTitle('Click Counter')

    with sc.Row('center'):
        with sc.Text('Click count: 0') as txt:
            @state.count.on_change
            def _():
                txt.text.set('Click count: {}'.format(state.count.get()))

        with sc.Button('Increase counter', type='primary') as btn:
            @btn.on_click
            def _():
                state.count.set(state.count.get() + 1)
                # or a shorthand form: state['count'] += 1

if __name__ == '__main__':
    sc.run(app, port=2201)
```

阅读 [用户手册](https://likianta.github.io/streamlit-canary/) 了解更多.

[^1]: 目前 (v0.4.x) 未完全覆盖 Streamlit 官方组件库, 功能仍在开发中.
