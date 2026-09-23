我们的 Streamlit Canary V3 组件的设计初衷是保持和 Streamlit 组件库的高度一致性.

但是随着 V3 组件库的迭代, 我们加入了独属于自己的新特性, 导致某些效果与 Streamlit 有所不同.

在此, 本文会详细列出所有差异/优化点, 当 AI Agent 在执行 `./test/pixel_fidelity` 测试时, 对于有疑问的部分, 应该优先参考本文来确认 "这是一个预期的差异还是一个待对齐的问题".

## UI 差异一览

- Control height (全局控件高度)
  - 按钮 (`v3.Button` / `v3.IconButton` / `v3.Popover` 与 `v3.MenuButton` 的触发器)、单行输入框 (`v3.TextInput` 的输入部分)、`v3.NumberInput` 的盒子、`v3.Selectbox` 的触发器、`v3.Multiselect` 的触发器、`v3.SegmentedControl` 的轨道, 以及共用一块状态区的 `v3.Callout` / `v3.Spinner`, 高度统一由 `runtime/static/css/01-base.css` 里的 `--st-control-height` (32px) 决定. 它在每一处都当作 `min-height` 用, 所以会增高的控件 (多行按钮文案, 换行的 alert) 仍然可以撑高 -- 例如两行文案的按钮实测 46.78px, 两行 alert 实测 51.19px.

    原版行为: st 的按钮与输入框是 40px (segmented 轨道则随自己的内边距落在 36.4px 之类的位置). 我们刻意矮 8px, 为的是让一行 / 一条工具栏里的框成为 "一条腰带", 而不是高低参差. 这是**既定选择**, 不要把它当成 bug 去 "修复" 回 40px: 像素对比里凡是上述控件的框高都应预期 32px. 由此产生的 8px 差值会连带影响依赖它们高度的一切纵向位置, 但那些位置都是前端按触发器的真实 rect 现算的 (面板 / 浮层的锚点, dropdown 的落点), 所以会自动跟随.

  - 一处实现上的耦合: `.st-text-input-box` 被三种语境复用 (TextInput 的输入框, NumberInput 的内层输入框, `TextInput(candidates=...)` 里被 Selectbox 触发器框住的那个). 后两者各有一条 override 把 `min-height` 归零, 让外框拥有高度 -- 新加类似复用时要照做, 否则内层会自己撑到 32px 并溢出外框.

- Height bounds (组件高度上下限)
  - 所有组件 (含布局容器) 都接受 `max_height` / `min_height` 两个像素上下限, 这是 canary 独有的能力. 上限会一并带上 `overflow: auto` -- 也就是说封顶的容器 / 面板会滚动, 而不是让内容溢出到盒子外面; 下限 (`min_height`) 没有这个副作用. `height='stretch'` 胜过上下限: 两者同时给时, 上下限被丢弃 (显式的"填满父级"优先). 细节与落地位置见 `AGENTS.md` §7.

    原版行为: st 没有"按元素设上下限"的入口 (只有 `st.container(height=...)` 这类固定高度), 所以这不是与 st 不一致, 而是我们多出来的能力. 像素对比时若看到某块区域被压住并出现滚动条, 先确认应用是否显式传了 `max_height`.

- Label visibility (label_visibility)
  - 我们给 `label_visibility` 多添了一个取值并把它作为默认: `'auto'` -- label 为空 (或只有空白) 时, 整个标签行连同它的高度一起收起来; label 有内容时等同 `'visible'`. 因为 `'auto'` 只看 label 文本, 空 label 即使带了 `help` 也会连同那个问号图标一起收起来 (要保住它就显式传 `'visible'`).

    原版行为 (在 :2200 上实测的 st): 默认的 `'visible'` 即使 label 是空字符串也会保留标签行 -- `st.text_input('')` 的控件高 68px (标签行 24px + 间隙 4px + 输入框 40px), 同一个控件改成 `label_visibility='collapsed'` 则是 40px. 所以**空 label 的控件**在我们这里会比 st 矮 28px. 现有场景里没有空 label 的控件, 以后新增场景时留意 (想要那 28px 就显式传 `'visible'`).

- Multiselect trigger (`height='fixed'`)
  - `v3.Multiselect` 的触发器**始终保持一行** (高度就是那个 32px 的控件高度): 选中的值排成一行, 放不下时横向滚动 (滚动条隐藏), 每勾选一次把值区滚到末尾. 这就是它的默认行为 (`height='fixed'`).

    原版行为: st 的 `st.multiselect` 用 `wrap: bool | None` 控制这件事 (它没有 `height` 参数): `None` (默认) 按布局决定 (在横向容器里或直接放在列里时, 标签单行 + 横向滚动; 其它情况换行), `True` 换行并且控件变高, `False` 单行固定高度 + 横向滚动. 我们是永远单行, 也就是 `wrap=False` 那一档. 所以像素对比时, 多选场景下的高度可能不同: 我们恒为 32px, st 在 `wrap=True` 或布局触发换行时会随标签增长. 这是有意为之, 不要按 st 去"修".

- Selectbox `width='content'` (按最宽的选项取宽)
  - `v3.Selectbox(width='content')` 的宽度按**最宽的选项**算, 不按当前显示的那个值: 否则选项长短不一时, 每切换一次触发器宽度就跳一次 (回归测试见 `test/selectbox_on_width_wrap.py`, 它断言每个选项下宽度一致, 且等于"最宽选项 + 框的内边距/边框/间隙/箭头"). 实现上有一处不可见的 sizer 与触发器共用 grid 单元格, 细节与两个坑 (`visibility: hidden` 而非 `display: none`; sizer 自己的 `width` 必须是 `auto`) 见 `AGENTS.md` §7.

    原版行为: st 的 `st.selectbox` 只接受 `"stretch"` 或 int (它的签名用的是 `WidthWithoutContent`), 根本没有 `'content'` 这个取值, 所以此处没有"与 st 对齐"可言 -- 这是我们多出来的能力. 像素对比时若发现宽度不一致, 先确认场景是否显式传了 `width='content'`.

- Layout gaps (全局横向 / 纵向间距)
  - 同目录 `01-base.css` 里还有两个间距 token: `--st-hgap` (8px) 与 `--st-vgap` (16px). 用横向的那个 (`--st-hgap`): `v3.Row` 子元素并排时的间距, `v3.Grid` 的列轨道之间, 横向 (`horizontal=True`) 的 `v3.Radio` / `v3.CheckGroup` 的选项之间, tab 条上的各个 tab, `v3.FloatingContainer` 聚簇内的子元素. 用纵向的那个 (`--st-vgap`): 应用根 (`#app`), `v3.Container`, `v3.Grid` 的行距及其 `GridCell`, popover 面板, expander 的正文, tab 面板. `v3.Row` 换行后那两行之间属于纵向节奏, 所以也走 `--st-vgap`. 注意: 属于控件自身尺度的间距 (按钮的文案到图标, checkbox 的框到文字) 不在此列, 它们保持各自原来的字面值.

    原版行为: 这些位置 st 用的都是 16px (主块容器 / `st.columns` / expander / 面板都是 1rem 的节奏). 我们把**横向**间距刻意收到 8px, 让并排的箱子读作一个聚簇而不是彼此散开; **纵向**间距保持 16px 与 st 一致. 所以像素对比里横向间距按 8px 预期, 纵向仍按 16px.

  - 一处跨端耦合: `Grid` 的列轨道宽度是服务端算出来的 (`runtime/render.py` 的 `_render_element`: `weight% - gap * (n - 1) / n`), 那个 `gap_px` 必须与 `--st-hgap` 同步, 否则 "轨道之和 + 间距之和" 不再等于容器内宽 (会差 `(16 - 8) * (n - 1) / n`; 3 列时约 5.3px/列). 实测 3 列 Grid 的轨道加间距为 703.98px, 容器内宽 704px.

- BottomContainer
  - 我们的底部布局容器是贴着当前的父布局的底部的: 实现是给容器加 `margin-top: auto`, 所以只要父级 (垂直容器) 还有剩余空间, 它就会被压到底部, 不限定于根布局. 我们同时给了 `v3.Bottom` 这个别名 (对齐原版的 `st.bottom`), `v3.BottomContainer` 仍然可用.

    原版行为: st.bottom 只允许在根布局中使用.

- Callout
  - `v3.Error` / `v3.Info` / `v3.Success` / `v3.Warning` 是同一个 `v3.Callout` 基类的四个子类, 四者只差配色 (子类只写 `_kind`, 渲染成 `.st-alert-<kind>`, 样式在 `runtime/static/css/11-status.css`). 四套配色逐一对照过真实的 Streamlit 应用 (`st.error` / `st.info` / `st.success` / `st.warning` 各渲染一条, 读计算样式): 背景是各自的 `--st-<name>-background-color`, 文字是各自的 `--st-<name>-text-color`; 浅色主题下实测背景为 blue `rgba(28,131,255,.1)` / green `rgba(33,195,84,.1)` / yellow `rgba(255,255,18,.1)` / red `rgba(255,43,43,.1)`, 文字为 `#0054a3` / `#158237` / `#926c05` / `#bd4043`. 注意 warning 是**黄色** (`--st-yellow-*`), 不是橙色.

  - 盒子的尺寸刻意与 Streamlit 不同: 我们固定 `min-height: var(--st-control-height)` (即 32px) + 内边距 `0 12px`, 原版是内边距 `16px` 且高度自适应.

    原版行为: st 的 alert 四周留 16px 内边距, 高度随内容撑开, 所以同样的文案在原版里更高一些. 我们让 alert 与普通按钮 / 输入框同高 (见上面 `Control height` 一节), 是为了让它和 Spinner 共用的那块状态区高度恒定 -- 状态在两行之间来回切换时不会跳动.

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

  - 簇内的子元素会丢掉自己的 `margin-bottom`: 簇是横向排列的, 纵向本就不需要间距; 而 `align-items: center` 居中的是 **margin 盒** —— 子元素若带底部外边距 (比如 `Popover` 的触发器有 8px), 它的可视部分就会被推离簇的中线 4px, 跟旁边的图标按钮看上去没有对齐. 该规则在页面样式末尾统一声明, 因此能盖过各组件自己那条单类选择器.

- Markdown
  - 当 `text` 为空 (或只有空白字符) 时, 组件整体隐藏, 不会留下一段空白的间距. 该字段是 bindable 的, 所以绑定了一个暂为空的来源时, 它会跟着来源的填充而重新出现.

    原版行为: st.markdown 在内容为空时仍然渲染出一个空的块级容器 (占据它的 margin 高度).

- MenuButton
  - 菜单面板与触发器之间的间距是紧凑的 4px (和原版 `st.menu_button` 一致).

    这是有意与 Popover 相反的取向: 菜单面板的元素 (选项列表) 样式固定、自定义程度低, 且选项列表与触发器紧密相关, 贴得近才让用户一眼看出它归属于这个触发器; 而 Popover 的面板里可以摆任意组件, 所以用了更宽松的 8px (见下面 Popover 一节).

- NumberInput
  - 当 NumberInput.step = 0 时, 不显示 stepper (-/+); 当 NumberInput.step > 0 时, 显示 stepper, 但如果此时组件尺寸过小, 则分两种情况: 比较窄, 则将 stepper 改为垂直方向排列 (上加下减), 非常窄, 则强制隐藏 stepper.

    原版行为: st.number_input 的 stepper 只要组件宽度 <= 7.5rem (其前端常量 `hideNumberInputControls`) 就直接隐藏, 没有竖排这一步.

- PdfViewer
  - 我们用自己打包的 pdf.js 把每一页画到 `<canvas>` 上 (引擎在 `runtime/static/pdfjs/`, 由 `/static/pdfjs/<name>` 送出; 只有真的出现 viewer 的页面才会按需下载约 1.6MB 的引擎). 服务器不做任何栅格化, 也不依赖任何 PDF 库.

    为什么不用浏览器自带的引擎 (渲染 `<embed type="application/pdf">`): 那条路线的实现是 —— 服务端用 `pikepdf` 把请求的页范围裁出来, 把裁好的字节交给 `Runtime.publish_media` 发布成 `/media/<内容哈希>`, 再把 URL 连同打开参数 (`#navpanes=0&zoom=page-width`, 即"不展开侧边栏 + 按宽度适配") 交给 `<embed>` (浏览器的默认是 `fit to page`, 那会把整页连页边一起塞进通常很矮的盒子里, 字小到看不清, 所以必须显式指定). 放弃它的原因是: viewer 的内容对页面不透明, 页面既量不到内容高度 (`height: auto` / `fit-content` 在 PDF `<embed>` 上会塌到替换元素通用的 150px), 也改不了它的样式, 于是 `height='content'` 只能靠"算" —— 每份文档一次 `pikepdf` 量高宽比, 再加两个 Chromium 实测的常数 (内置 viewer 自身的留白), 换个浏览器就会差几十 px; 而且它要求浏览器带 PDF 插件 (测试用的 headless chromium 就没有插件, `<embed>` 在那里画不出任何内容), `pages_to_render` 也只能在服务端裁 (`pikepdf`), 因为 `<embed>` 无法被告知该显示哪几页.

    pdf.js 这条路线没有上述任何一条限制: 内容高度是真的 (canvas 撑出来的), 换任何浏览器都一致, `pages_to_render` 由前端负责跳过多余的页, 所以服务端不需要 PDF 库, 也不需要插件. 详细的取舍写在 `components_v3/media.py` 的 `_to_url` 上方的技术备忘里.

  - 原版行为: `st.pdf` 只是第三方 `streamlit-pdf` 包的薄封装, 参考应用 `pdf_watermaker` 预览用的是另一个第三方包 `streamlit_pdf_viewer.pdf_viewer`; 两者都要在 iframe 里装进一整套 pdf.js (约 2MB) 才能画出第一页, 且打开时的缩放是 pdf.js 自己的默认值.

  - `pages_to_render` 由前端在渲染时跳过不需要的页, 因此它限制的是"画多少", 不是"传多少"; 不传则画整份文档.

    原版行为: `streamlit_pdf_viewer` 把整份文档 base64 后交给前端, 由 pdf.js 决定渲染哪几页 —— 传输量不随 `pages_to_render` 减少 (这点我们现在与原版一致).

  - 页面是我们自己画的 canvas, 所以面板只套一层主题边框 + 圆角 (`runtime/static/css/70-media.css`), 不改变 `width` / `height` 指定的盒尺寸.

    原版行为: viewer 的"外框" (工具栏, 页面四周的灰色底) 属于 pdf.js, 是它自己那套工具栏和背景色 —— 因此 `pdf_viewer_vs.py` 有意**不**比较这部分.

  - `height='content'` 让盒子高到刚好包住内容, 再由 `max_height` 封顶: 内容不足上限就贴住内容 (Expander 之类的父容器正好包住它, 没有滚动条), 超过上限就停在 `max_height` 并在盒子内部滚动. **只给 `max_height` 不给 `height` 就隐含这个模式** —— 给了一个上限却不给高度时, "按内容" 是唯一说得通的高度. (默认值仍是 `_default_height = 500`: 那是一个固定的高度, 所以 `max_height=1500` 落在 500 的盒子上永远不会生效, 正是它让人误以为 "不到 1500 就 overflow 了".)

    这里没有几何推算: canvas 的高度就是内容高度, 所以 `height='content'` 是货真价实的 "内容多高就多高", 也不再需要 `?ratio=` 之类的旁路参数.

  - 页面脚本 (`76-pdf-viewer.js`) 复用一份文档缓存 (最多 4 份, 超出即 `destroy()`), `ResizeObserver` 在宽度变化时按新宽度重画, 所以拖拽缩放最终只触发一次重绘.

- Popover
  - Popover 的展开面板使用高度动画 (120ms), 跟 Selectbox 的展开面板是同一套做法: 从 0 高度展开到内容高度, 展开过程中内容被裁剪, 因此不会溢出, 也不会出现滚动条 (展开结束后若内容超过 max-height, 才恢复为可滚动).

    原版行为: st.popover 的面板是瞬间出现的, 没有展开动画.

  - 面板与触发器之间的间距是 8px (宽松).

    原版行为: st.popover 的面板待在触发器下方 4px. 这个 8px 是我们的既定选择 -- popover 的面板里可以摆任意组件, 效果丰富, 离触发器太近会显得局促, 所以留了更宽松的间距. `compare_popover_layout.py` 以 `TOP_MARGIN_SC = 8` / `TOP_MARGIN_ST = 4` 显式断言, 面板内部的纵向位置则统一按"相对面板顶边"的偏移来对比, 不受这 4px 影响. (对比 MenuButton 的紧凑 4px, 见上面 `MenuButton` 一节.)

  - `panel_align='row'` 的行对齐面板 (`TreeSelectWithInput` 用的那种) 用 `overflow-y: scroll` 常驻滚动条槽位, 并且**只**对高度做动画 (`st-popover-panel-grow-in`). 它的工具栏右对齐, 位于滚动条内侧 -- 若滚动条等动画放完才出现, 最后一帧上工具栏会横移一个滚动条宽度. 常驻槽位让面板从第一帧起就可滚动, 于是不再有位移. 代价是内容不足一屏时也留着一道空槽 (无头浏览器的覆盖式滚动条下约 2px, 经典滚动条下约 15px). (其它面板仍是"展开过程中裁剪、结束后才可滚动", 见上面第一条.)

- RadioGroup
  - 当鼠标悬浮在选项上时, 选项整行背景高亮, 就像 Selectbox 展开后的选项一样: 高亮盒子用 `padding: 0 8px 0 4px` 配反向 `margin-left: -4px` 撑开, 因此悬浮时盒子会向左侧溢出一点, 但选项本身 22.4px 的行距不变 (静止态的排版与原版一致). 盒子在竖直方向不超出选项 -- 这样上下相邻的高亮既不会重叠 (重叠会让半透明色叠加成更深的一条), 也不会让下面的选项抢走上面选项的点击.

    原版行为: 鼠标略过时, 只有开头的圆圈形状的颜色会稍稍变深.

  - 点击某个选项行后, 该行保持 "高亮" (`is-highlighted`, 见 `scHighlightChoice`), 直到点击另一行或列表重建; 行下标同时通过 `focus` 事件回传 (见 `focused_index`). 当"被高亮的选项"和"被悬浮的选项"上下相邻时, 两者的高亮背景会 "融合" 成一个圆角矩形: 上面选项去掉底部圆角, 下面选项去掉顶部圆角, 共享边既没有圆角也没有颜色叠加 (原版没有这个效果).

  - 选项列表为空时, 画一行灰色提示 "No options to select." (对齐 `st.radio`: 一个未勾选的指示器 + 14px 的 `fadedText40` 文案), 而不是留白.

  - 勾选不经过脚本: 整行就是 box 自己的 `<label>`, 由浏览器原生切换, 因此点下去即生效, 既没有"等第二击"的延迟也没有闪烁. 这也意味着没有双击手势 -- 需要"进入某个节点"的组件自己另外画一个按钮 (见下面 `TreeSelect` 的 `->`).

    原版行为: 原版同样没有行手势, 但它的 checkbox / radio 也是 `<label>` 包裹, 双击照样切换两次, 视觉上闪两下.

- Selectbox
  - Selectbox 在展开后, 会对当前已选择的选项的文字以主题色高亮显示.

    原版行为: st.selectbox 的所有选项的文字都是默认色.

  - Selectbox.accept_new_option 会在展开的面板内的第一行显示一个输入组件.

    原版行为: st.selectbox 允许用户直接在触发器上输入文字, 但会跟折叠/展开操作混合, 体验不是很好.

  - Selectbox 的展开面板使用高度动画 (120ms): 从 0 高度展开到内容高度, 展开过程中内容被裁剪, 因此不会溢出, 也不会出现滚动条 (展开结束后若内容超过 max-height, 才恢复为可滚动). 同时 chevron 图标旋转 180 度 (80ms, 比面板更快), 因此不会出现 "面板已经展开, 而 chevron 还没转到位" 的情况.

    原版行为: st.selectbox 的 chevron 在展开/折叠时保持不动, 仅靠面板的开合来提示状态; 面板也是瞬间出现的, 没有展开动画.

  - Selectbox 输入框连续点击, 可以反复折叠/展开. 跟 Popover 的按钮行为一致 (触发器文字设置为 `user-select: none`, 因此连续点击不会变成文字选择状态).

    原版行为: 只有连续点击 chevron 图标, 才能折叠/展开. 重复点击输入框, 会变成文字选择状态. 这是因为原版的 accept_new_options 功能与设计耦合导致的缺陷.

  - 触发器的宽度可能比原版宽 8px: 因为我们在"当前值"与 chevron 之间留了 8px 的最小间距 (`gap: 8px`), 原版没有这一段. 触发器的宽度是内容撑出来的 (场景没显式给宽度时), 所以这 8px 直接体现在宽度上, 并连带影响展开面板与面板内条目的宽度.

    原版行为: st.selectbox 的值与 chevron 之间没有间距, 因此内容撑宽时它的触发器比我们窄 8px. 像素对比中若看到触发器 / 面板 / 高亮框的宽度差 8px, 就是这一处; 注意高亮框相对**它自己的**触发器的内缩量两版是一致的 (约 12px), 这也是 `compare_selectbox_expanded.py` 的断言口径.

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

  - [不是差异, 记在这里以免被 "修" 回去] 表格外框是圆角, 且与原版取值相同. 我们的 `.st-table-scroll` 取 `border-radius: var(--st-base-radius)` (8px, 与带边框的 `Container` 同值); 原版包住 `<table>` 的那个滚动盒子实测也是 `border-radius: 8px` (`overflow: auto`, `border-top-width: 1px`). 因为该盒子本就 `overflow: auto`, 浏览器会把表格自身的方角裁到弧内 -- 带底色的表头行 (`header_background=True`) 也跟着圆弧, 不会从角上探出去.

- Theme
  - 两套主题 (浅色 / 深色) 各自声明 `color-scheme` (`light` / `dark`), 让浏览器把我们没有自己绘制的界面 -- 滚动条, 文本光标, 以及应用之外的画布 -- 也按当前主题上色. 否则暗色模式下 `Popover` 面板 (行对齐面板的常驻滚动条槽位) 与 `Code` 代码块的滚动条仍是亮色, 跟四周的深色格不入.

    例外: Selectbox 展开面板自己画了一道 6px 的细滚动条 (`::-webkit-scrollbar*`), 不走系统绘制, 所以不受 `color-scheme` 影响.

- Toast
  - 多个 toast 会在右上角堆叠成一小摞: 最新的一条在最前面完整显示, 更早的按离最新的层级逐层缩小 (0.96 / 0.92 / 0.88 / 0.84) 并从后方探出下边缘 (最多保留 5 条, 超出时丢弃最早的). 鼠标进入时这一摞会展开成等距 (15px) 的完整列表, 离开时收拢, 展开/收拢伴随动画. 效果完全由 CSS 实现: 容器用 `column-reverse` 让最新的一条占据顶端锚位, 折叠态再用负的 `margin-top` 把每条 toast 叠到新一条下面, 缩放则用 `nth-last-child` 按层级递减; hover 时把间距和缩放都还原. 每条 toast 右侧有一个 ✕, 仅在 hover 时出现, 用于移除它. (参考了 "Pines" toast 的效果.)

  - 不需要自己声明 `v3.Toast()`: `sc.toast(...)` 在任何地方都能用, 它写的是页面唯一的那一摞 toast (app 没声明时由 runtime 在 build 后补一个). 只有想自己控制这个元素的位置或手动驱动时才需要显式声明.

  - 每条 toast 都带 `duration` (参考 st.toast): `'short'` = 4 秒, `'long'` = 10 秒, `'infinite'` = 直到用户关闭, 或一个正整数秒数. 倒计时结束会自动移除; 鼠标进入这一摞时暂停计时, 离开后按剩余时间继续.

    原版行为: st.toast 只能显示一条信息, 且动效简单.

- Toolbar
  - 右上角的 ⋮ 菜单是我们的开发者工具 (参考 Streamlit 主菜单做的简化版), 只有两项: 主题切换 (System / Light / Dark) 和 Rerun. 主题切换完全在浏览器端完成 (页面同时携带两套主题, 按 `html[data-theme]` 作用域), 选择会写进 localStorage, 选 System 时跟随操作系统的浅色/深色偏好; Rerun 会重新执行服务端进程, 这也是替代 file watcher 的主动手段.

    原版行为: st 的主菜单项更多 (Rerun / Settings / Print / Record a screencast / About 等), 主题切换在 Settings 面板里; 源码变更时原版会在右上角弹出提示条.

## 后端关键差异一览

- 我们使用 `enabled` 来控制组件可交互性, 而原版是 `disabled`.
- NumberInput 的 stepper 需要显式设置 `step` 参数才会显示.
- `v3.Radio` 更名为 `v3.RadioGroup` (名字与 `v3.CheckGroup` 对称). `Radio` 作为别名指向 `RadioGroup`.
- `v3.Toggle` 更名为 `v3.ToggleBox`; `Toggle` 保留为别名 (`Toggle = ToggleBox`), 所以现有 `v3.Toggle` 写法照常可用. 仅换名字, 行为与外观不变 (DOM 类名仍是 `st-toggle`).
- 我们新增了 `v3.CheckGroup` (多选的分组控件, 样式与 `v3.RadioGroup` 一致, 但选项用方形 box 且可多选); 原版没有对应组件. 它还多一个 `focused_index` 属性 (被点击文本 "高亮" 的那一行的下标, -1 表示无), 便于 "进入高亮节点" 这类按钮: `btn.enabled = sc.bind(cg.focused_index, lambda i: i >= 0)`. 另外 `cg.on_change` 是 `cg.value.on_change` (即 `cg['on_value']`) 的简写 —— 组件上一个 `on_change` 属性, 免得写长串 (注意这是**组件级**的便利属性, 目前只有 `CheckGroup` 有; 别的组件还是走 `cg['on_value']`).
- `v3.CheckGroup` 的 `options` 也接受 `dict[str, bool]`: 键直接充当选项文本, 值表示该选项初始是否勾选. 这种 (flag 模式) 下 `.value` 不再是 `options` 的子集, 而是与 `options` **平行的一串 bool** —— 客户端回报的仍然是勾选文本, 由 `_coerce_value` 翻译成这串 bool; 服务端渲染与前端补丁都靠 `st-check-group--flags` 这个类名按位置读勾选状态, 所以 `options` 变更时服务端要把当前 flags 一并塞进 options 补丁 (`msg.flags`), 否则重建出来的行会全部掉勾. 普通的 list / tuple 形式完全不受影响 (`value` 仍是选项的子集).
- 我们新增了 `v3.ReducibleGroup` (用 `v3.MenuButton` 选项行的样式, 但每行右侧多一个悬浮时才出现的 `x`, 点击即把该项从列表移除并发出 `on_reduce`); 原版没有对应组件.
- `v3.MenuButton` 对齐 `st.menu_button`: 选项行 `min-width: 128px`, 行距 32px (28px 行高 + 4px 会折叠的 margin), 菜单面板 `padding: 2px 6px` / 圆角 12px / `z-index: 1000060`, 触发按钮的 chevron 比 `st.popover` 大一号 (20px vs 16px). 菜单面板与触发器的间距是紧凑的 4px (和原版一致), 刻意区别于 `v3.Popover` 的宽松 8px (见上面 `MenuButton` / `Popover` 两节).
- `v3.TextInput` 多一个 `candidates` 参数: 给出候选列表后, 文本框右侧出现一个 caret, 展开的面板与外框完全复用 `v3.Selectbox` 的样式, 选一项即写回文本框. 文本始终可自由输入, 所以它相当于 `st.selectbox(..., accept_new_options=True)`, 只是值不必是候选之一. `None` 无 caret, 空列表有 caret 但禁用 (是否有 caret 在构建时定下, 之后的 patch 只替换列表内容). 另外 `v3.TextInput` 现在按 Enter 即提交 (原版 `st.text_input` 也是如此). `v3:TreeSelect:PathInput` 也支持这个参数, 但默认关闭 (不传即 `None`, 是一个纯文本框): 祖先跳转改由面板顶部的 selectbox 承担 (见下一条), 两个入口是重复的. `v3.TextInput` 另有一个 `accept_new_option` 参数 (单数, 与 `format_new_option` 对齐): 面板顶部多一行 "Add: ...", 其内容随文本框同步, 取用它等于在框里按回车 (发的是 `submit` 而不是候选人那种 `change`); 没有 `candidates` 时它会连 caret 一起带出来. `v3:TreeSelect:PathInput` 默认打开它, 于是从外部粘贴一个路径也能被面板接住 (见下一条).
- `v3.TreeSelect` 去掉了箭头工具栏, 改为"点行勾选 + 箭头导航": 列表头部固定一行 `..` (去父目录), 其后才是文件夹 (名字带 `/`) 与文件. 点行只勾选/选中该行 (多选模式下整行都是 box 的 label, 所以点正文即勾选; 单选模式下点正文即选中); 进入某个文件夹不再靠双击, 而是悬停该行时在正文右侧浮出的 `->` 按钮 (见下一条). `..` 既不是可勾选的节点也不是文件夹: 它的 box 被冻结, 单击行正文即回到上级 (它不画箭头). 单选列表每次重建都从"未选中"开始, 这样点任意一行都能生效.
- `v3.TreeSelect` 的文件夹导航由一个悬浮箭头承担: 若一行的选项能被 `navigable` 断言命中, 渲染时就多画一个 `<button class="st-row-open">` (`_row_enter_html` / `scRowEnterHtml`), 静止时 `opacity: 0`, 鼠标进入该行才浮现 (正文右侧, 间隔 32px = 行自身的 8px `gap` + 额外的 24px, 给"box + 名字"这块 tick 区留出呼吸空间), 浮现动画是"淡入 + 右移 4px"; 箭头用 `:blue[..]` 的颜色, 鼠标移到箭头上时正文出现 `:gray[..]` 色的下划线, 箭头自己的小方块背景转成 `:blue[..]` 的底色 `--st-blue-background-color` (它压在行的 hover 底色之上, 所以必须带蓝才分得开). 箭头右边还有 30px 容错区 (由 `::after` 撑出, 属于按钮本身): 悬停/点击都算"点箭头", 因为否则要瞄准一个 20px 的图标; 再往右 (far right) 才回到行自己的点击行为. 所有箭头落在同一个 x 上: `scAlignRowArrows` 把每个带箭头行的正文 `min-width` 设成"当前最长的 folder 名", 所以指针不用逐行重读也能瞄准. 这一步要重算三次 —— 首次渲染、字体加载完 (字宽会变), 以及**元素由隐藏变可见时** (popover 打开 / `visible` 翻转): `display: none` 的子树里一切宽度都量到 0, 隐藏时算出来的对齐是无效的. 另外, 一行的选项若能被 `body_opens` 断言命中 (`..`), 它的**整行点击**就走 `scOpenRow`, 和点箭头同一个手势 —— box 冻结了, 这次点击本来就没别的事可做 (所以 `..` 不画箭头, 单击它就是回到上级). 这两个手势都是 `TreeSelect` 私有基类 `_NavigationGroup` (及其两个子类 `_NavCheckGroup` / `_NavRadioGroup`) 提供的, 通用型 `CheckGroup` / `RadioGroup` 完全不知情.
- `v3.TreeSelect:selection_mode` 决定一次能选多少: `'single'` (单选节点, 默认), `'multiple'` (只勾选当前文件夹, 跳转会清空), `'multicross'` (跨文件夹累加进 bucket); 也可以给一个元组/列表 (如 `('single', 'multicross')`), 意思是"就这几个模式, 用 SegmentedControl 切换", 并以**第一个**为初始模式 —— 顺序任你排. (早先那个 `'any'` 已按 TODO 移除, 它等价于给全三种.) 结果统一读 `.value` —— `single` 是 `str`, 其余是路径 `list`; `mode` 给出当前模式. 面板顶部是一行工具栏: 最前面是一个 "Current location" selectbox, 列出当前文件夹的**所有祖先节点** (自身排在最后, 所以这串阶梯同时就是"你在哪"), 选中任意一级即跳转; 其后随模式增减 —— refresh 恒有, bucket 只在这组模式含 `multicross` 时, SegmentedControl 只在给了不止一个模式时. Confirm 按钮 (`type='primary'`) 的位置由 `_vendored` 决定: 独立的 `TreeSelect` 把它摆在列表正下方 (常规流内, 撑满面板宽度), 面板自带一圈边框 (`border`, 默认 `True`); 被包装器塞进 popover 的那种 (`TreeSelectWithInput` 传 `_vendored=True`) 则把按钮浮到右下角 (`FloatingContainer('bottom-right')`) 并 `border=False`, 免得在 popover 自己的框里再套一层. 点击发出 `TreeSelect.on_submit` —— 包装器 (`TreeSelectWithInput`) 监听它来收起自己的 Browse popover. 手输/粘贴/选择文件夹路径 = 跳到该目录; 手输/粘贴一个文件则跳到它所在的文件夹并把它的那一行标记出来 (被过滤器丢掉的类型没有行可标, 列表就停在最顶上), 同时该文件进入选中.
- `v3.RadioGroup` / `v3.CheckGroup` 的选项行可以携带三个按行判定的谓词, 渲染时各算成类名/属性并通过 `options` 补丁以"命中下标列表"的形式推给前端 (JS 无法求值 Python 谓词, 和 `box_disabled` 同一机制): `box_disabled` 把命中的选项的 box 冻结 (字段 disabled + 行加 `.is-box-disabled`, 画得暗一些), `navigable` 让命中的行多出上面那个 `->` 箭头, `body_opens` 让命中的行把整行点击从"高亮"换成"进入" (走 `scOpenRow`). 另外 `RadioGroup` 也有 `focused_index` (和 `CheckGroup` 一致); 这份行状态 (点击高亮 + `focus` 事件回传) 抽到了私有基类 `_RowGestures`. 行上不再有任何双击手势: `on_open` 现在只在 `_NavigationGroup` 上定义, 由箭头 (或 `body_opens` 行的整行点击) 触发.
- `TreeSelectWithInput` / `TreeSelectDualPaneWithInput` 的 "Recent" 下拉: 列表被替换时, 内部 radio 会自己 adopt 最新一条 (`_auto_select`), 而这次 adopt 看起来跟"用户挑了一项"一模一样 —— 以前包装器会因此跑一遍 `_commit`, 于是"面板里勾一个文件夹"会把面板一起带走. 现在 `Recent` 用与 `_auto_select` 相同的判据预先记下它将 adopt 哪一项, 回传时跳过它: 列表刷新不再伪装成挑选, 而真·下拉挑选仍照常 `_commit` (文件夹 → 面板跳过去, 文件 → 加入选中).
- 我们新增了 `v3.FloatingContainer` (`v3.Floating` 是它的别名): 吸附在父布局某个角落的容器, 见上面 UI 差异一节的 `FloatingContainer`.
- 我们新增了 `v3.ToggleButton`: 一个 `Button` 子类, 点击即翻转它自己的 `value` (`Property[bool]`), 并据此换装 —— `value` 为真画 `primary`, 为假画 `secondary` (借既有的 `type` patch 就地换类). 它**没有** `type` 参数: 那个字段由 `value` *派生* 且只读 (`_shared._derive` / `_ReadOnlyProperty`, 写它会抛 `AttributeError`), 所以二者不会脱节; `on_click` 的处理器在翻转之后才跑, 读到的就是点击后的新状态. 原版没有对应组件 (`st.button` 不持有状态, `st.toggle` 又不长成按钮的样子).
- `v3.Popover` 多一个 `close()` 方法: popover 的开合状态本来只存在于浏览器端 (触发器负责开合, 点外部关闭), 服务端读不到, 所以 `close()` 只是把一个 `_close` 计数器 +1 并推给前端, 前端收到这个 patch 就把面板折起来 (触发器保持原位). `TreeSelectWithInput` 的 Confirm 就是靠它收起面板.
- `visible` 是 **组件基类** 的属性: `Component.__init__` 统一声明 (默认 True, 可绑定), `Component.is_hidden()` 是唯一解释它的地方. 因此任何组件都能 `visible=...`, 渲染端也只在 `render._render` 一处把 `hidden` 打到根元素上. 有一族组件的 `visible` 是「内容非空」与构造参数的 **AND** (`_visible_when_filled`): 内容为空 (字面为空, 见 `_is_blank`) 即隐藏, 显式 `visible=False` 也隐藏 (两者都满足才渲染). 它们是 `Code` / `Markdown` / `Table` / `PdfViewer` / `LogPanel`, 以及**全部文本元素** (`Text` / `Title` / `Caption` / `PageTitle`, 由 `_HelpText` 统一提供) 和 `Callout` 族 (`Info` / `Error` / `Success` / `Warning`). 因此空白文本不再留空框, 其 `visible` 参数默认都是 **True**. 想要像 `st.title('')` 那样占住一整行 (原版空 title 仍渲染一个空 `h1`), 就写一个空格占位符 (`v3.Title(' ')`) -- 空格算内容, 不算空 (只有真正为空 / `None` 才隐藏). 两个例外是 `Spinner` / `Progress`: 它们的 `visible` 默认 **False** (是显式的开关, 不由内容决定), 因为那是"用时才现身"的指示器. (`PageTitle` 即使被隐藏也仍按它的 `text` 命名标签页, 见 `render._find_page_title`.)
- 我们新增了 `v3.LogPanel` (原版没有对应组件): 把 app 写到终端的内容 (`source='stdout'` 默认, 或 `'stderr'`) 实时搬到页面上 —— 一行一条, 最新的在底部, 并随新行滚动保持在视口内. 缓冲区上限 `_max_lines` (500), 满了丢最旧的; 一行都没有时面板自己隐藏, 所以不打印的 app 不会多出一个空框. 捕获要包两层: 替换 `sys.stdout` / `sys.stderr`, 同时把 neoprint 在导入时就存下的那个句柄 (`neoprint.console._stdout`, 被 `Console.print` 读取) 也指向同一个 tee —— 只换 `sys.stdout` 的话, 凡是从 `streamlit_canary` 内部打印、被 neoprint 加了装饰的输出都会绕过 tee; 反过来 tee 总是先照常写回真正的流, 终端输出不受影响. tee 另外按行缓冲, 因为 `print(a, b)` 是一段段 `write` 进来的, 而面板要的是整行. 行尾/行中的 ANSI 颜色码会被丢掉: 浏览器没有终端来解释它们, 留着只会显示成乱码 (所谓"去掉颜色码, 纯文本显示").
