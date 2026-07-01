"""
tests/test_config.py
----------------------
Tests for config.py: locating Tesseract/Poppler across PATH and the
Homebrew/MacPorts fallback directories used on macOS.
"""

from pathlib import Path

import config


class TestFindExecutable:
    def test_finds_via_shutil_which(self, monkeypatch):
        monkeypatch.setattr(config.shutil, "which", lambda name: f"/usr/bin/{name}")
        assert config._find_executable("tesseract") == "/usr/bin/tesseract"

    def test_returns_none_when_not_found_anywhere(self, monkeypatch):
        monkeypatch.setattr(config.shutil, "which", lambda name: None)
        monkeypatch.setattr(config.sys, "platform", "linux")
        assert config._find_executable("does-not-exist-anywhere") is None

    def test_macos_homebrew_fallback_is_used_when_path_misses_it(self, monkeypatch, tmp_path):
        # Simulate: not on PATH (as happens when an app is double-clicked
        # from Finder), but present in a Homebrew-style directory.
        fake_bin = tmp_path / "opt_homebrew_bin"
        fake_bin.mkdir()
        (fake_bin / "tesseract").write_text("#!/bin/sh\n")

        monkeypatch.setattr(config.shutil, "which", lambda name: None)
        monkeypatch.setattr(config.sys, "platform", "darwin")
        monkeypatch.setattr(config, "CANDIDATE_MACOS_DIRECTORIES", [str(fake_bin)])

        found = config._find_executable("tesseract")
        assert found == str(fake_bin / "tesseract")

    def test_macos_fallback_is_not_used_on_other_platforms(self, monkeypatch, tmp_path):
        fake_bin = tmp_path / "opt_homebrew_bin"
        fake_bin.mkdir()
        (fake_bin / "tesseract").write_text("#!/bin/sh\n")

        monkeypatch.setattr(config.shutil, "which", lambda name: None)
        monkeypatch.setattr(config.sys, "platform", "linux")
        monkeypatch.setattr(config, "CANDIDATE_MACOS_DIRECTORIES", [str(fake_bin)])

        assert config._find_executable("tesseract") is None


class TestCheckExternalDependencies:
    def test_no_warnings_when_everything_is_found(self, monkeypatch):
        monkeypatch.setattr(config, "TESSERACT_CMD", "/usr/bin/tesseract")
        monkeypatch.setattr(config.shutil, "which", lambda cmd: cmd)
        monkeypatch.setattr(config.os.path, "isfile", lambda p: True)
        monkeypatch.setattr(config, "_locate_poppler", lambda: "/usr/bin/pdftoppm")

        assert config.check_external_dependencies() == []

    def test_warns_about_missing_tesseract(self, monkeypatch):
        monkeypatch.setattr(config, "TESSERACT_CMD", "/nonexistent/tesseract")
        monkeypatch.setattr(config.shutil, "which", lambda cmd: None)
        monkeypatch.setattr(config.os.path, "isfile", lambda p: False)
        monkeypatch.setattr(config, "_locate_poppler", lambda: "/usr/bin/pdftoppm")

        warnings = config.check_external_dependencies()
        assert len(warnings) == 1
        assert "Tesseract" in warnings[0]

    def test_warns_about_missing_poppler(self, monkeypatch):
        monkeypatch.setattr(config, "TESSERACT_CMD", "/usr/bin/tesseract")
        monkeypatch.setattr(config.shutil, "which", lambda cmd: cmd)
        monkeypatch.setattr(config.os.path, "isfile", lambda p: True)
        monkeypatch.setattr(config, "_locate_poppler", lambda: None)

        warnings = config.check_external_dependencies()
        assert len(warnings) == 1
        assert "Poppler" in warnings[0]

    def test_warns_about_both_when_both_missing(self, monkeypatch):
        monkeypatch.setattr(config, "TESSERACT_CMD", "/nonexistent/tesseract")
        monkeypatch.setattr(config.shutil, "which", lambda cmd: None)
        monkeypatch.setattr(config.os.path, "isfile", lambda p: False)
        monkeypatch.setattr(config, "_locate_poppler", lambda: None)

        warnings = config.check_external_dependencies()
        assert len(warnings) == 2


class TestLocatePoppler:
    def test_finds_pdftoppm_in_configured_poppler_path(self, monkeypatch, tmp_path):
        bin_dir = tmp_path / "poppler_bin"
        bin_dir.mkdir()
        exe_name = "pdftoppm.exe" if config.os.name == "nt" else "pdftoppm"
        (bin_dir / exe_name).write_text("#!/bin/sh\n")

        monkeypatch.setattr(config, "POPPLER_PATH", str(bin_dir))
        found = config._locate_poppler()
        assert found == str(bin_dir / exe_name)
