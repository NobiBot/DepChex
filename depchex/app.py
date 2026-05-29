from textual.app import App
from textual.screen import Screen
from textual.widgets import Header, Footer, Button, Input, Static, ProgressBar, RichLog, DataTable
from textual.containers import Vertical, Horizontal
from textual import work
from rich.text import Text
import subprocess
from .models import Package, Risk
from .scanner import scan_project, is_github_url, parse_github_url


class WelcomeScreen(Screen):
    def compose(self):
        yield Header()
        yield Vertical(
            Static("DepChex", classes="title"),
            Static("Enter a local path or GitHub URL to scan for dependency confusion risks."),
            Input(placeholder="Path or GitHub URL (e.g. /home/user/project or https://github.com/owner/repo)", id="path-input"),
            Horizontal(
                Button("Paste", id="paste-btn"),
                Button("Scan", id="scan-btn", variant="primary"),
                id="button-row",
            ),
            id="welcome-container",
        )
        yield Footer()

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "scan-btn":
            path = self.query_one("#path-input", Input).value
            if path:
                self.app.push_screen(ScanningScreen(path))
        elif event.button.id == "paste-btn":
            try:
                text = subprocess.run(
                    ["wl-paste"], capture_output=True, text=True, timeout=2
                ).stdout.strip()
                if text:
                    self.query_one("#path-input", Input).value = text
            except (FileNotFoundError, subprocess.TimeoutExpired):
                pass

    def on_input_submitted(self, event: Input.Submitted):
        path = event.value
        if path:
            self.app.push_screen(ScanningScreen(path))


class ScanningScreen(Screen):
    def __init__(self, path: str):
        super().__init__()
        self.project_path = path
        self.results: list[Package] = []

    def _display_name(self) -> str:
        if is_github_url(self.project_path):
            owner, repo = parse_github_url(self.project_path)
            return f"{owner}/{repo}"
        return self.project_path

    def compose(self):
        yield Header()
        yield Vertical(
            Static(f"Scanning: {self._display_name()}"),
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

        def on_progress(pkg, i, total):
            progress.update(total=total, progress=i + 1)
            log.write(f"{pkg.name}  →  {pkg.risk.name}")

        self.results = scan_project(self.project_path, progress_callback=on_progress)
        self.app.call_from_thread(
            self.app.push_screen, ResultsScreen(self.results)
        )


class ResultsScreen(Screen):
    def __init__(self, results: list[Package]):
        super().__init__()
        self.results = results

    def compose(self):
        confirmed = sum(1 for p in self.results if p.risk == Risk.CONFIRMED)
        suspicious = sum(1 for p in self.results if p.risk == Risk.SUSPICIOUS)
        yield Header()
        yield Vertical(
            Static(f"Scan complete — {confirmed} confirmed, {suspicious} suspicious, {len(self.results)} total"),
            DataTable(id="results-table"),
            Horizontal(
                Button("New Scan", id="new-scan-btn", variant="primary"),
                id="button-row",
            ),
        )
        yield Footer()

    def on_mount(self):
        table = self.query_one("#results-table", DataTable)
        table.add_columns("Package", "Source", "Risk", "Releases")
        for pkg in self.results:
            if pkg.pypi_releases is not None and pkg.pypi_first_release:
                release_str = f"{pkg.pypi_releases} ({pkg.pypi_first_release[:4]})"
            elif pkg.pypi_exist is True:
                release_str = "found"
            elif pkg.pypi_exist is False:
                release_str = "—"
            else:
                release_str = "?"

            if pkg.risk == Risk.CONFIRMED:
                risk_cell = Text("CONFIRMED", style="bold red")
            elif pkg.risk == Risk.SUSPICIOUS:
                risk_cell = Text("SUSPICIOUS", style="bold yellow")
            else:
                risk_cell = Text("SAFE", style="green")

            table.add_row(pkg.name, pkg.source_file, risk_cell, release_str)

    def on_button_pressed(self, event: Button.Pressed):
        if event.button.id == "new-scan-btn":
            self.app.pop_screen()
            self.app.pop_screen()


class DepChexApp(App):
    def on_ready(self):
        self.push_screen(WelcomeScreen())


def main():
    app = DepChexApp()
    app.run()


if __name__ == "__main__":
    main()

