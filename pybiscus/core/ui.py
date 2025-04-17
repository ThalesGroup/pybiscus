from rich.console import Console

class UI:

    def __init__(self):
        self.console = Console()

    def log(self, contentToLog):
        self.console.log(contentToLog)

pybiscus_ui = UI()
