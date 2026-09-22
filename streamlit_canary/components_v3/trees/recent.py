"""The "Recent" dropdown: the folders this browser has been in."""

import typing as tp

from ..inputs import RadioGroup
from ..layouts import Popover
from ...kernel import Property


class Recent(Popover):
    """The "Recent" dropdown: the last picked paths, newest first.

        recent = Recent('Recent', options=[], visible=has_history)
        ...
        @recent.value.on_change
        def _on_pick(): ...

    The caller owns the list: assign `options` to replace it (usually from its
    own `_TreeNav`) and bind `visible` to whether there is any history.  A
    pick mirrors into `value`.

    Args:
        label: the trigger's label.
        options: the remembered paths (bindable).
        max_height: cap in px on the list, after which it scrolls.
        visible: whether the trigger is shown (default False — a history
            dropdown has nothing to show until the caller fills it in).

    Properties:
        options: list — the remembered paths (bindable).
        value: str — the picked path ('' while nothing is picked).

    Signals:
        on_value (via `recent['on_value']` or `recent.value.on_change`)
    """

    def __init__(
        self,
        label: str = 'Recent',
        options: tp.Sequence[str] = (),
        *,
        max_height: int = 280,
        visible: bool | Property = False,
        **kwargs: tp.Any,
    ) -> None:
        super().__init__(label, visible=visible, **kwargs)

        initial = list(options)
        self.options = Property(initial)
        self.value = Property('')
        # The radio runs its own `_auto_select` whenever the list changes,
        # which takes the first entry. That is a list refresh, not a pick --
        # but it looks exactly like one to `_sync_value`, and a listener
        # treating it as a pick would move the panel. So remember the entry
        # the radio is about to take on its own.
        self._adopting = ''
        with self:
            self._radio = RadioGroup(
                label,
                options=initial,
                label_visibility='collapsed',
                max_height=max_height,
            )

        @self.options.on_change
        def _sync_options() -> None:
            options_ = list(self.options.get() or [])
            # same test as `_auto_select`, so the guess below is exact
            if options_ and self._radio['value'] not in options_:
                self._adopting = str(options_[0])
            self._radio.options.set(options_)

        @self._radio.value.on_change
        def _sync_value() -> None:
            picked = str(self._radio['value'])
            if picked and picked == self._adopting:
                self._adopting = ''
                return
            self.value.set(picked)

        if initial:
            self._radio.value.set(initial[0])
