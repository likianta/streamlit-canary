我们的 Streamlit Canary V3 组件的设计初衷是保持和 Streamlit 组件库的高度一致性.

但是随着 V3 组件库的迭代, 我们加入了独属于自己的新特性, 导致某些效果与 Streamlit 有所不同.

在此, 本文会详细列出所有差异/优化点, 当 AI Agent 在执行 `./test/pixel_fidelity` 测试时, 对于有疑问的部分, 应该优先参考本文来确认 "这是一个预期的差异还是一个待对齐的问题".

## UI 差异一览

- TODO: BottomContainer
  - TODO: 我们的底部布局容器是贴着当前的父布局的底部的.

    原版行为: st.bottom 只允许在根布局中使用.

- NumberInput
  - 当 NumberInput.step = 0 时, 不显示 stepper (-/+); 当 NumberInput.step > 0 时, 显示 stepper, 但如果此时组件尺寸过小, 则分两种情况: 比较窄, 则将 stepper 改为垂直方向排列 (上加下减), 非常窄, 则强制隐藏 stepper.

    原版行为: st.number_input 的 stepper 只要组件宽度 <= 7.5rem (其前端常量 `hideNumberInputControls`) 就直接隐藏, 没有竖排这一步.

- Popover
  - Popover 的展开面板使用高度动画 (120ms), 跟 Selectbox 的展开面板是同一套做法: 从 0 高度展开到内容高度, 展开过程中内容被裁剪, 因此不会溢出, 也不会出现滚动条 (展开结束后若内容超过 max-height, 才恢复为可滚动).

    原版行为: st.popover 的面板是瞬间出现的, 没有展开动画.

- Radio
  - TODO: 当鼠标悬浮在选项上时, 选项背景色高亮, 就像 Selectbox.expanded.item 一样.

    原版行为: 鼠标略过时, 只有开头的圆圈形状的颜色会稍稍变深.

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
  - TODO: Table 的单元格带有一些 padding.

    原版行为: st.table 的单元格几乎没有 padding, 导致 st.table(..., width='content') 时, 单元格的文字内容几乎紧挨着表格边框了.

  - TODO: Table 支持自定义 title, caption, footer 以及 header row 样式 (注: 自定义样式不是高度自定义, 而是提供有限的样式参数来调整).

- TODO: Toast
  - TODO: 多个 toast 信息堆叠显示, 当鼠标进入时, 会展开成多条信息列表, 鼠标进入/离开伴随展开/堆叠动画.

    原版行为: st.toast 只能显示一条信息, 且动效简单.

## 后端关键差异一览

- 我们使用 `enabled` 来控制组件可交互性, 而原版是 `disabled`.
- NumberInput 的 stepper 需要显式设置 `step` 参数才会显示.
