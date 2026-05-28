from textual.app import App
from textual.screen import Screen
from textual.widgets import Header, Footer, Button, Input, Static, ProgressBar, RichLog, DataTable
from textual.containers import Vertical, Horizontal
from textual import work
from models import Package, Risk
from scanner import parse_deps, check_pypi, looks_internal


class WelcomeScreen(Screen):
    def compose(self):
        yield Header()
        yield Vertical(
            Static("DepChex", classes="title"),
            Static("Enter the path to a Python project to scan for dependency confusion risks."),
            Input(placeholder="Path to project (e.g. /home/user/myproject or .)", id="path-input"),
            Button("Scan", id="scan-btn", variant="primary"),
            id="welcome-container",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "scan-btn":
            path = self.query_one("#path-input", Input).value
            if path:
                self.app.push_screen(ScanningScreen(path))
    def on_input_submitted(self, event: Input.Submitted):
        path = event.value
        if path:
            self.app.push_screen(ScanningScreen(path))

class ScanningScreen(Screen):
    def __init__(self, path: str):
        super().__init__()
        self.project_path = path
        self.results: list[Package] = []
    def compose(self):
        yield Header()
        yield Vertical(
            Static(f"Scanning: {self.project_path}"),
            ProgressBar(total=100, id="progress", show_eta=False),
            RichLog(id="log", highlight=True, markup=True),
        )
        yield Footer()
    def on_mount(self):
        self.run_scan()
    @work(exclusive=True, thread=True)
    async def run_scan(self):
        log = self.query_one("#log", RichLog)
        progress = self.query_one("#progress", ProgressBar)
        deps = parse_deps(self.project_path)
        progress.update(total=len(deps))
        results = []
        for i, pkg in enumerate(deps):
            log.write(f"Checking {pkg.name}...")
            pkg.pypi_exist = check_pypi(pkg.name)
            if looks_internal(pkg.name) and pkg.pypi_exist:
                pkg.risk = Risk.CONFIRMED
            results.append(pkg)
            progress.update(progress=i + 1)
            label = "CONFIRMED" if pkg.risk == Risk.CONFIRMED else "SAFE"
            log.write(f"  {label}")
        self.results = results
        self.app.call_from_thread(
            self.app.push_screen, ResultsScreen(self.results)
        )
class ResultsScreen(Screen):
    def __init__(self, results: list[Package]):
        super().__init__()
        self.results = results
    def compose(self):
        yield Header()
        yield Vertical(
            Static(f"Scan complete — {sum(1 for p in self.results if p.risk == Risk.CONFIRMED)} confirmed risk(s)"),
            DataTable(id="results-table"),
        )
        yield Footer()
    def on_mount(self):
        table = self.query_one("#results-table", DataTable)
        table.add_columns("Package", "Source", "On PyPI?", "Risk")
        confirmed_count = 0
        for pkg in self.results:
            pypi_str = "Yes" if pkg.pypi_exist else "No"
            risk_str = pkg.risk.name
            row = table.add_row(pkg.name, pkg.source_file, pypi_str, risk_str)
            if pkg.risk == Risk.CONFIRMED:
                table.update_cell(row, "Risk", "CONFIRMED")
                confirmed_count += 1
class DepChexApp(App):
    def on_ready(self):
        self.push_screen(WelcomeScreen())
def main():
    app = DepChexApp()
    app.run()





if __name__ == "__main__":
    main()
