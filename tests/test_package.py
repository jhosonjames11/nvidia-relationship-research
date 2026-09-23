from nvidia_research import __version__
from nvidia_research.cli import main


def test_package_exports_a_nonempty_version() -> None:
    assert __version__ == "0.1.0"


def test_cli_help_exits_successfully(capsys) -> None:
    assert main(["--help"]) == 0
    assert "NVIDIA relationship research" in capsys.readouterr().out
