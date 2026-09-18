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

- FloatingContainer
  - 我们的新组件 (原版没有): 一簇组件 "吸附" 在父布局的某个角落 (`top-left` / `top-center` / `top-right` / `bottom-left` / `bottom-center` / `bottom-right`), 内部子组件横向排列. 它用 `position: sticky` 实现: 父布局滚动时它停在那个角落不动, 同时保留自己在文档流里的位置 -- 所以父布局不需要额外的补偿 padding, 任何一行都能滚动到不被它永久遮挡. 它带一层与面板/弹窗同色的背景, 滚动过去的行不会从它下面透出来.

  - 只能放进垂直布局 (`Column` / `Container` / `Popover` / `Dialog` / 根布局), 放进 `Row` 会抛 `ValueError`: 角落的横向对齐靠的是 `align-self`, 而 `Row` 的 flex 方向会与之打架.

  - sticky 只能相对元素自身的流位置做偏移, 所以 `top-*` 簇要写成父布局的第一个子元素, `bottom-*` 簇要写成最后一个 (bottom 簇另外带 `margin-top: auto`, 父布局还有富余空间时也会被压到底部).

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

  - `CheckGroup(body_click_behavior='')` 下, 当"被高亮的选项"和"被悬浮的选项"上下相邻时, 两者的高亮背景会 "融合" 成一个圆角矩形: 上面选项去掉底部圆角, 下面选项去掉顶部圆角, 共享边既没有圆角也没有颜色叠加 (原版没有这个效果).

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
- `v3.TreeSelect` 去掉了箭头工具栏, 改为"点行导航": 列表头部固定一行 `..` (去父目录), 其后才是文件夹 (名字带 `/`) 与文件; 单点导航模式下它后面还跟一行 `.` (当前目录, 只选中不跳转). 上下移动都只需一次点击 (v1 的 `tree_select` 也是这套 `.` 设计), 单选列表每次重建都从"未选中"开始, 这样点任意一行都能生效.
- `v3.TreeSelect:navigation_mode` 决定"移动"用哪个手势. `'single_click'` 是老行为 (一次点击既移动又选中, 由 box 独自承担勾选); `'double_click'` (默认) 则是一次点击只勾选/选中该行 (多选模式下整行都是 box 的 label, 点正文即勾选; 单选模式下点正文即选中), 双击才进入文件夹. 文件双击没有动作 (无处可去); `.` 行被去掉 (勾选与移动既然分开, 一个只为"同时做两件事"而存在的行就没有意义了); `..` 仍然能上去, 但它的 box 被冻结 —— 变暗且永不勾选, 单点正文只高亮, 双击才跳转 (它是导航目标, 不是节点). 注意: 双击多选行是"两次勾选相抵", 所以双击进入文件夹不会顺带把它勾进 bucket; 单选行是 radio, 双击则会让它保持选中 (桌面文件管理器的习惯).
- `v3.TreeSelect:selection_mode` 决定一次能选多少: `'single'` (单选节点, 默认), `'multiple'` (只勾选当前文件夹, 跳转会清空), `'multicross'` (跨文件夹累加进 bucket), `'any'` (三者在 SegmentedControl 里自由切换). 结果统一读 `.value` —— `single` 是 `str`, 其余是路径 `list`; `mode` 给出当前模式. 右上角浮动的工具栏随模式增减: refresh 恒有, bucket 只在 `multicross` / `any`, SegmentedControl 只在 `any`; 右下角另外浮着一个 Confirm 按钮 (`type='primary'`), 点击发出 `TreeSelect.on_submit` —— 包装器 (`TreeSelectWithInput`) 监听它来收起自己的 Browse popover. 手输/选择文件夹路径 = 跳到该目录 (所以选中祖先候选即导航), 文件才进入选中.
- `v3.CheckGroup(body_click_behavior='')` 的"正文点击"覆盖整行 (box 自身除外), 不再只有文字: box = 勾选, 行的其余位置 = 交给应用 (例如点文件夹的正文进入该目录); 被点行的下标仍通过 `focused_index` 回传.
- `v3.RadioGroup` / `v3.CheckGroup` 多两个参数服务上面的 `double_click` 模式: `double_click_open` 让行正文的**双击**通过 `on_open` 回报行下标 (单点仍走原来的路径), `box_disabled` 是一个断言, 把命中的选项的 box 冻结 (字段 disabled + 行加 `.is-box-disabled`, 画得暗一些). 另外 `RadioGroup` 现在也有 `focused_index` (之前只有 `CheckGroup` 有); 两个类的这份行状态抽到了私有基类 `_RowGestures`.
- `TreeSelectWithInput` / `TreeSelectDualPaneWithInput` 的 "Recent" 下拉: 列表被替换时, 内部 radio 会自己 adopt 最新一条 (`_auto_select`), 而这次 adopt 看起来跟"用户挑了一项"一模一样 —— 以前包装器会因此跑一遍 `_commit`, 于是"面板里勾一个文件夹"会把面板一起带走 (双击模式的单击语义就是这么被破坏的). 现在 `Recent` 用与 `_auto_select` 相同的判据预先记下它将 adopt 哪一项, 回传时跳过它: 列表刷新不再伪装成挑选, 而真·下拉挑选仍照常 `_commit` (文件夹 → 面板跳过去, 文件 → 加入选中).
- 我们新增了 `v3.FloatingContainer` (`v3.Floating` 是它的别名): 吸附在父布局某个角落的容器, 见上面 UI 差异一节的 `FloatingContainer`.
- `v3.Popover` 多一个 `close()` 方法: popover 的开合状态本来只存在于浏览器端 (触发器负责开合, 点外部关闭), 服务端读不到, 所以 `close()` 只是把一个 `_close` 计数器 +1 并推给前端, 前端收到这个 patch 就把面板折起来 (触发器保持原位). `TreeSelectWithInput` 的 Confirm 就是靠它收起面板.
- `visible` 现在是**组件基类**的属性: `Component.__init__` 统一声明 (默认 True, 可绑定), `Component.is_hidden()` 是唯一解释它的地方. 因此任何组件都能 `visible=...`, 渲染端也只在 `render._render` 一处把 `hidden` 打到根元素上 (以前每个 renderer 各写一遍, 且只有部分组件支持 —— 给 `Text` / `Button` / `SegmentedControl` 之类传 `visible=` 会直接 `TypeError`). `Column` / `Dialog` / `Expander` / `Popover` / `MenuButton` / `Progress` / `Spinner` 等原本各自声明的那份已经删掉. 例外: `Code` / `Markdown` / `Table` 的 `visible` 是「内容非空」与构造参数的**与** —— 内容为空即隐藏, 显式 `visible=False` 也隐藏 (两者都满足才渲染).
