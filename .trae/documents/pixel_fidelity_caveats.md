我们的 Streamlit Canary V3 组件的设计初衷是保持和 Streamlit 组件库的高度一致性.

但是随着 V3 组件库的迭代, 我们加入了独属于自己的新特性, 导致某些效果与 Streamlit 有所不同.

在此, 本文会详细列出所有差异/优化点, 当 AI Agent 在执行 `./test/pixel_fidelity` 测试时, 对于有疑问的部分, 应该优先参考本文来确认 "这是一个预期的差异还是一个待对齐的问题".

## UI 差异一览

- BottomContainer
  - 我们的底部布局容器是贴着当前的父布局的底部的: 实现是给容器加 `margin-top: auto`, 所以只要父级 (垂直容器) 还有剩余空间, 它就会被压到底部, 不限定于根布局.

    原版行为: st.bottom 只允许在根布局中使用.

- Code
  - 当 `text` 为空 (或只有空白字符) 时, 组件整体隐藏, 不会留下一个空的代码框. 该字段是 bindable 的, 所以绑定了一个暂为空的来源时, 它会跟着来源的填充而重新出现.

    原版行为: st.code 在内容为空时仍然绘制出代码框 (占据一块高度).

- Exception
  - 组件的事件处理函数 (signal handler) 抛出的未捕获异常, 会被 runtime 捕获 (否则会让 websocket 断开, 前端再也收不到后续的 patch), 用 `traceback.format_exception` 转成完整文本后推送到前端, 显示在右上角的浮层里: 标题是异常文本的最后一行 (如 `Exception: Test error`), 正文是完整 traceback, 右下角带一个 Rerun 按钮, 点击即重启进程并刷新页面, 这样就 "忽略了这个错误, 重新运行"; 同时 traceback 也会写到服务端 stderr.

    原版行为: st 是 rerun 模型, 脚本执行期间的异常直接显示在页面正文里 (红色的 Exception 面板 + `Traceback:` + 源码行), 用户按 `R` 或点击右上角菜单的 Rerun 重新执行脚本.

- Markdown
  - 当 `text` 为空 (或只有空白字符) 时, 组件整体隐藏, 不会留下一段空白的间距. 该字段是 bindable 的, 所以绑定了一个暂为空的来源时, 它会跟着来源的填充而重新出现.

    原版行为: st.markdown 在内容为空时仍然渲染出一个空的块级容器 (占据它的 margin 高度).

- MenuButton
  - 菜单面板与触发器之间的间距是紧凑的 4px (和原版 `st.menu_button` 一致).

    这是有意与 Popover 相反的取向: 菜单面板的元素 (选项列表) 样式固定、自定义程度低, 且选项列表与触发器紧密相关, 贴得近才让用户一眼看出它归属于这个触发器; 而 Popover 的面板里可以摆任意组件, 所以用了更宽松的 8px (见下面 Popover 一节).

- NumberInput
  - 当 NumberInput.step = 0 时, 不显示 stepper (-/+); 当 NumberInput.step > 0 时, 显示 stepper, 但如果此时组件尺寸过小, 则分两种情况: 比较窄, 则将 stepper 改为垂直方向排列 (上加下减), 非常窄, 则强制隐藏 stepper.

    原版行为: st.number_input 的 stepper 只要组件宽度 <= 7.5rem (其前端常量 `hideNumberInputControls`) 就直接隐藏, 没有竖排这一步.

- Popover
  - Popover 的展开面板使用高度动画 (120ms), 跟 Selectbox 的展开面板是同一套做法: 从 0 高度展开到内容高度, 展开过程中内容被裁剪, 因此不会溢出, 也不会出现滚动条 (展开结束后若内容超过 max-height, 才恢复为可滚动).

    原版行为: st.popover 的面板是瞬间出现的, 没有展开动画.

  - 面板与触发器之间的间距是 8px (宽松).

    原版行为: st.popover 的面板待在触发器下方 4px. 这个 8px 是我们的既定选择 -- popover 的面板里可以摆任意组件, 效果丰富, 离触发器太近会显得局促, 所以留了更宽松的间距. `compare_popover_layout.py` 以 `TOP_MARGIN_SC = 8` / `TOP_MARGIN_ST = 4` 显式断言, 面板内部的纵向位置则统一按"相对面板顶边"的偏移来对比, 不受这 4px 影响. (对比 MenuButton 的紧凑 4px, 见上面 `MenuButton` 一节.)

- RadioGroup
  - 当鼠标悬浮在选项上时, 选项整行背景高亮, 就像 Selectbox 展开后的选项一样: 高亮盒子用 `padding: 0 8px 0 4px` 配反向 `margin-left: -4px` 撑开, 因此悬浮时盒子会向左侧溢出一点, 但选项本身 22.4px 的行距不变 (静止态的排版与原版一致). 盒子在竖直方向不超出选项 -- 这样上下相邻的高亮既不会重叠 (重叠会让半透明色叠加成更深的一条), 也不会让下面的选项抢走上面选项的点击.

    原版行为: 鼠标略过时, 只有开头的圆圈形状的颜色会稍稍变深.

  - `CheckGroup(full_body_click=False)` 下, 当"被高亮的选项"和"被悬浮的选项"上下相邻时, 两者的高亮背景会 "融合" 成一个圆角矩形: 上面选项去掉底部圆角, 下面选项去掉顶部圆角, 共享边既没有圆角也没有颜色叠加 (原版没有这个效果).

  - 选项列表为空时, 画一行灰色提示 "No options to select." (对齐 `st.radio`: 一个未勾选的指示器 + 14px 的 `fadedText40` 文案), 而不是留白.

- Selectbox
  - Selectbox 在展开后, 会对当前已选择的选项的文字以主题色高亮显示.

    原版行为: st.selectbox 的所有选项的文字都是默认色.

  - Selectbox.accept_new_options 会在展开的面板内的第一行显示一个输入组件.

    原版行为: st.selectbox 允许用户直接在触发器上输入文字, 但会跟折叠/展开操作混合, 体验不是很好.

  - Selectbox 的展开面板使用高度动画 (120ms): 从 0 高度展开到内容高度, 展开过程中内容被裁剪, 因此不会溢出, 也不会出现滚动条 (展开结束后若内容超过 max-height, 才恢复为可滚动). 同时 chevron 图标旋转 180 度 (80ms, 比面板更快), 因此不会出现 "面板已经展开, 而 chevron 还没转到位" 的情况.

    原版行为: st.selectbox 的 chevron 在展开/折叠时保持不动, 仅靠面板的开合来提示状态; 面板也是瞬间出现的, 没有展开动画.

  - Selectbox 输入框连续点击, 可以反复折叠/展开. 跟 Popover 的按钮行为一致 (触发器文字设置为 `user-select: none`, 因此连续点击不会变成文字选择状态).

    原版行为: 只有连续点击 chevron 图标, 才能折叠/展开. 重复点击输入框, 会变成文字选择状态. 这是因为原版的 accept_new_options 功能与设计耦合导致的缺陷.

- Tab
  - 切换 tab 时, tab indicator line 使用变速动画: 线条先拉伸到覆盖新旧两个 tab, 再收缩到新 tab 上 (每段都是先快后慢的 quad 曲线, 营造出 "粘性" 的拖拽感), 总时长 200ms.

    原版行为: st.tab 的 tab indicator line 是简单的平移动画.

- Table
  - 单元格带有比原版更明显的 padding, 且按 "贴哪条边框" 区分: 单元格到内部分隔线 (分隔两列的竖直边框) 的距离是 8px, 到表格外框的距离是 16px. 因此在 st.table(..., width='content') 时, 单元格的文字不会紧贴表格边框, 且贴着外框的一侧留白更宽.

    原版行为: st.table 的单元格有 padding, 但很小 (`th` 为 `4px 6px 4px 8px`, `td` 为 `4px 6px`, 上下只有 4px). 当 st.table(..., width='content') 时, 单元格的文字内容几乎紧挨着表格边框, 肉眼容易误以为它 "没有 padding".

  - Table 支持自定义 title, caption, footer 以及 header row 样式 (注: 自定义样式不是高度自定义, 而是提供有限的样式参数来调整): `title` / `caption` 渲染在表格上方, `footer` 渲染在表格下方; `header=(label, ...)` 增加一行列标题 (每列一个标签), `header_background=True` 给该行加表头底色. 这些字段都是 bindable 的, 变化时前端就地更新.

  - Table 的每一行可以是 N 个单元格 (第一个是行标题, 其余是数据列), 因此支持 N 列表格: 2 元组即 `st.table(dict)` 那种两列表格, 三元组即三列表格.

  - 当 `rows` 为空时, 组件整体隐藏 (空表格不占据空间). 该字段是 bindable 的, 所以 `v3.Table(sc.bind(state.record))` 在 record 为空时会隐藏, 一旦有数据就重新出现.

    原版行为: st.table 在数据为空时仍然绘制出一个空表格 (占据一块高度).

- Toast
  - 多个 toast 会在右下角堆叠成一小摞: 最新的一条在最前面完整显示, 更早的按离最新的层级逐层缩小 (0.96 / 0.92 / 0.88 / 0.84) 并从后方探出上边缘 (最多保留 5 条, 超出时丢弃最早的). 鼠标进入时这一摞会展开成等距 (15px) 的完整列表, 离开时收拢, 展开/收拢伴随动画. 效果完全由 CSS 实现: 折叠态用负的 `margin-top` 把每条 toast 叠到前一条上面, 缩放则用 `nth-last-child` 按层级递减; hover 时把间距和缩放都还原. 每条 toast 右侧有一个 ✕, 仅在 hover 时出现, 用于移除它. (参考了 "Pines" toast 的效果.)

  - 每条 toast 都带 `duration` (参考 st.toast): `'short'` = 4 秒, `'long'` = 10 秒, `'infinite'` = 直到用户关闭, 或一个正整数秒数. 倒计时结束会自动移除; 鼠标进入这一摞时暂停计时, 离开后按剩余时间继续.

    原版行为: st.toast 只能显示一条信息, 且动效简单.

- Toolbar
  - 右上角的 ⋮ 菜单是我们的开发者工具 (参考 Streamlit 主菜单做的简化版), 只有两项: 主题切换 (System / Light / Dark) 和 Rerun. 主题切换完全在浏览器端完成 (页面同时携带两套主题, 按 `html[data-theme]` 作用域), 选择会写进 localStorage, 选 System 时跟随操作系统的浅色/深色偏好; Rerun 会重新执行服务端进程, 这也是替代 file watcher 的主动手段.

    原版行为: st 的主菜单项更多 (Rerun / Settings / Print / Record a screencast / About 等), 主题切换在 Settings 面板里; 源码变更时原版会在右上角弹出提示条.

## 后端关键差异一览

- 我们使用 `enabled` 来控制组件可交互性, 而原版是 `disabled`.
- NumberInput 的 stepper 需要显式设置 `step` 参数才会显示.
- `v3.Radio` 更名为 `v3.RadioGroup` (名字与 `v3.CheckGroup` 对称). `Radio` 作为别名指向 `RadioGroup`.
- 我们新增了 `v3.CheckGroup` (多选的分组控件, 样式与 `v3.RadioGroup` 一致, 但选项用方形 box 且可多选); 原版没有对应组件. 它还多一个 `focused_index` 属性 (被点击文本 "高亮" 的那一行的下标, -1 表示无), 便于 "进入高亮节点" 这类按钮: `btn.enabled = sc.bind(cg.focused_index, lambda i: i >= 0)`.
- 我们新增了 `v3.ReducibleGroup` (用 `v3.MenuButton` 选项行的样式, 但每行右侧多一个悬浮时才出现的 `x`, 点击即把该项从列表移除并发出 `on_reduce`); 原版没有对应组件.
- `v3.MenuButton` 对齐 `st.menu_button`: 选项行 `min-width: 128px`, 行距 32px (28px 行高 + 4px 会折叠的 margin), 菜单面板 `padding: 2px 6px` / 圆角 12px / `z-index: 1000060`, 触发按钮的 chevron 比 `st.popover` 大一号 (20px vs 16px). 菜单面板与触发器的间距是紧凑的 4px (和原版一致), 刻意区别于 `v3.Popover` 的宽松 8px (见上面 `MenuButton` / `Popover` 两节).
- `v3.TextInput` 多一个 `candidates` 参数: 给出候选列表后, 文本框右侧出现一个 caret, 展开的面板与外框完全复用 `v3.Selectbox` 的样式, 选一项即写回文本框. 文本始终可自由输入, 所以它相当于 `st.selectbox(..., accept_new_options=True)`, 只是值不必是候选之一. `None` 无 caret, 空列表有 caret 但禁用 (是否有 caret 在构建时定下, 之后的 patch 只替换列表内容). `v3:TreeSelect:PathInput` 用它列出当前文件夹的所有祖先路径, 便于一步跳到任意上级; 列表在提交文本或面板导航后刷新. 另外 `v3.TextInput` 现在按 Enter 即提交 (原版 `st.text_input` 也是如此).
- `v3.TreeSelect` 去掉了箭头工具栏, 改为"点行即导航": 列表头部固定两行 `..` (去父目录) 和 `.` (当前目录, 只选中不跳转), 其后才是文件夹 (名字带 `/`) 与文件. 上下移动都只需一次点击 (v1 的 `tree_select` 也是这套 `.` 设计), 单选列表每次重建都从"未选中"开始, 这样点任意一行都能生效.
- `v3.TreeSelect:select_mode` 决定一次能选多少: `'single'` (单选节点, 默认), `'multiple'` (只勾选当前文件夹, 跳转会清空), `'multicross'` (跨文件夹累加进 bucket), `'any'` (三者在 SegmentedControl 里自由切换). 结果统一读 `.value` —— `single` 是 `str`, 其余是路径 `list`; `mode` 给出当前模式. 面板顶部工具栏随模式增减: refresh 恒有, bucket 只在 `multicross` / `any`, SegmentedControl 只在 `any`. 手输/选择文件夹路径 = 跳到该目录 (所以选中祖先候选即导航), 文件才进入选中.
- `v3.CheckGroup(full_body_click=False)` 的"正文点击"覆盖整行 (box 自身除外), 不再只有文字: box = 勾选, 行的其余位置 = 交给应用 (例如点文件夹的正文进入该目录); 被点行的下标仍通过 `focused_index` 回传.
