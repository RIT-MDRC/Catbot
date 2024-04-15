from rich.text import TextType
from textual.message import Message
from textual.widgets import Button
from typing_extensions import Literal

ButtonVariant = Literal["default", "primary", "success", "warning", "error"]


class ReactiveButton(Button):
    def __init__(
        self,
        label: TextType | None = None,
        variant: ButtonVariant = "default",
        on_blur: callable = None,
        *,
        name: str | None = None,
        id: str | None = None,
        classes: str | None = None,
        disabled: bool = False,
    ):
        super().__init__(
            label=label,
            variant=variant,
            name=name,
            id=id,
            classes=classes,
            disabled=disabled,
        )
        self.on_btn_blur = on_blur

    class Active(Message):
        def __init__(self, button):
            self.button: ReactiveButton = button
            super().__init__()

        @property
        def control(self):
            return self.button

    class Released(Message):
        def __init__(self, button):
            self.button: ReactiveButton = button
            super().__init__()

        @property
        def control(self):
            return self.button

    def on_focus(self):
        self.post_message(ReactiveButton.Active(self))

    def on_click(self):
        self.post_message(ReactiveButton.Released(self))
        if self.on_btn_blur:
            self.on_btn_blur()
        else:
            self.blur()
