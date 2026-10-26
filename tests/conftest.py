import platform

import pytest


def pytest_addoption(parser):
    parser.addoption("--run-hardware", action="store_true", help="Explicitly allow live Windows microphone/loopback capture")
    parser.addoption("--run-ui", action="store_true", help="Launch real Tkinter windows for UI smoke checks")


def pytest_collection_modifyitems(config, items):
    for item in items:
        if "hardware" in item.keywords and not config.getoption("--run-hardware"):
            item.add_marker(pytest.mark.skip(reason="Live capture requires explicit --run-hardware and a provisioned Windows device"))
        if "ui" in item.keywords and not config.getoption("--run-ui"):
            item.add_marker(pytest.mark.skip(reason="GUI smoke checks require --run-ui and a desktop session"))
