from textual.app import App
from textual.widgets import Footer, Header


class Main_UI(App):

    BINDINGS = [("d", "toggle_dark", "Toggle dark mode")]

    def compose(self):
        yield Header()
        yield Footer()

    def action_toggle_dark(self):
        self.dark = not self.dark


if __name__ == "__main__":
    Main_UI().run()
