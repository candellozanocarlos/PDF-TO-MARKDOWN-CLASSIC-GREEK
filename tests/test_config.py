"""
tests/test_config.py
----------------------
Tests for config.py: locating Tesseract/Poppler across PATH and the
Homebrew/MacPorts fallback directories used on macOS, and the winget
fallback directories used on Windows.
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

    def test_windows_fixed_directory_fallback_is_used(self, monkeypatch, tmp_path):
        # Simulate the default Tesseract-OCR install directory not being
        # on PATH, as happens with a double-clicked packaged .exe.
        #
        # sys.platform is monkeypatched too (not just os.name): on a real
        # Mac/Linux CI runner sys.platform stays "darwin"/"linux" unless
        # we change it, so without this the macOS branch (checked first)
        # would run instead of the Windows one we are trying to test here.
        fake_dir = tmp_path / "Tesseract-OCR"
        fake_dir.mkdir()
        (fake_dir / "tesseract.exe").write_text("stub\n")

        monkeypatch.setattr(config.shutil, "which", lambda name: None)
        monkeypatch.setattr(config.sys, "platform", "win32")
        monkeypatch.setattr(config.os, "name", "nt")
        monkeypatch.setattr(config, "CANDIDATE_WINDOWS_DIRECTORIES", [str(fake_dir)])
        monkeypatch.setattr(config, "_winget_search_roots", lambda: [])

        found = config._find_executable("tesseract.exe")
        assert found == str(fake_dir / "tesseract.exe")

    def test_windows_winget_links_fallback_is_used(self, monkeypatch, tmp_path):
        # Simulate a portable package winget just installed: a symlink (or
        # here, a plain file standing in for one) in its per-user "Links"
        # directory, which is not yet on PATH for our already-running app.
        links_dir = tmp_path / "WinGet" / "Links"
        links_dir.mkdir(parents=True)
        (links_dir / "pdftoppm.exe").write_text("stub\n")

        monkeypatch.setattr(config.shutil, "which", lambda name: None)
        monkeypatch.setattr(config.sys, "platform", "win32")
        monkeypatch.setattr(config.os, "name", "nt")
        monkeypatch.setattr(config, "CANDIDATE_WINDOWS_DIRECTORIES", [])
        monkeypatch.setattr(config, "_winget_search_roots", lambda: [links_dir])

        found = config._find_executable("pdftoppm.exe")
        assert found == str(links_dir / "pdftoppm.exe")

    def test_windows_fallbacks_are_not_used_on_other_platforms(self, monkeypatch, tmp_path):
        fake_dir = tmp_path / "Tesseract-OCR"
        fake_dir.mkdir()
        (fake_dir / "tesseract.exe").write_text("stub\n")

        monkeypatch.setattr(config.shutil, "which", lambda name: None)
        monkeypatch.setattr(config.sys, "platform", "linux")
        monkeypatch.setattr(config.os, "name", "posix")
        monkeypatch.setattr(config, "CANDIDATE_WINDOWS_DIRECTORIES", [str(fake_dir)])

        assert config._find_executable("tesseract.exe") is None


class TestHomebrewHelpers:
    def test_available_true_on_macos_when_brew_found(self, monkeypatch):
        monkeypatch.setattr(config.sys, "platform", "darwin")
        monkeypatch.setattr(config, "_find_executable", lambda name: "/opt/homebrew/bin/brew")
        assert config.homebrew_available() is True

    def test_available_false_on_other_platforms(self, monkeypatch):
        monkeypatch.setattr(config.sys, "platform", "win32")
        monkeypatch.setattr(config, "_find_executable", lambda name: "/opt/homebrew/bin/brew")
        assert config.homebrew_available() is False

    def test_missing_packages_lists_both_when_neither_is_found(self, monkeypatch):
        monkeypatch.setattr(config, "_find_executable", lambda name: None)
        monkeypatch.setattr(config, "_locate_poppler", lambda: None)
        packages = config.missing_homebrew_packages()
        assert "tesseract" in packages
        assert "tesseract-lang" in packages
        assert "poppler" in packages

    def test_missing_packages_empty_when_both_are_found(self, monkeypatch):
        monkeypatch.setattr(config, "_find_executable", lambda name: "/opt/homebrew/bin/" + name)
        monkeypatch.setattr(config, "_locate_poppler", lambda: "/opt/homebrew/bin/pdftoppm")
        assert config.missing_homebrew_packages() == []


class TestVcRedistHelpers:
    def test_installed_true_when_dll_present(self, monkeypatch, tmp_path):
        system32 = tmp_path / "System32"
        system32.mkdir()
        (system32 / "vcruntime140.dll").write_text("stub\n")
        monkeypatch.setenv("SystemRoot", str(tmp_path))
        assert config._vcredist_installed() is True

    def test_installed_false_when_dll_missing(self, monkeypatch, tmp_path):
        (tmp_path / "System32").mkdir()
        monkeypatch.setenv("SystemRoot", str(tmp_path))
        assert config._vcredist_installed() is False


class TestWingetHelpers:
    def test_available_true_on_windows_when_winget_found(self, monkeypatch):
        monkeypatch.setattr(config.os, "name", "nt")
        monkeypatch.setattr(config.shutil, "which", lambda name: r"C:\WinGet\winget.exe")
        assert config.winget_available() is True

    def test_available_false_on_other_platforms(self, monkeypatch):
        monkeypatch.setattr(config.os, "name", "posix")
        monkeypatch.setattr(config.shutil, "which", lambda name: r"C:\WinGet\winget.exe")
        assert config.winget_available() is False

    def test_missing_packages_lists_all_three_ids_when_nothing_is_found(self, monkeypatch):
        monkeypatch.setattr(config, "_vcredist_installed", lambda: False)
        monkeypatch.setattr(config, "_find_executable", lambda name: None)
        monkeypatch.setattr(config, "_locate_poppler", lambda: None)
        packages = config.missing_winget_packages()
        assert config.WINGET_PACKAGE_IDS["vcredist"] in packages
        assert config.WINGET_PACKAGE_IDS["tesseract"] in packages
        assert config.WINGET_PACKAGE_IDS["poppler"] in packages

    def test_missing_packages_empty_when_everything_is_found(self, monkeypatch):
        monkeypatch.setattr(config, "_vcredist_installed", lambda: True)
        monkeypatch.setattr(config, "_find_executable", lambda name: r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        monkeypatch.setattr(config, "_locate_poppler", lambda: r"C:\poppler\Library\bin\pdftoppm.exe")
        assert config.missing_winget_packages() == []

    def test_missing_packages_lists_only_vcredist_when_only_that_is_missing(self, monkeypatch):
        monkeypatch.setattr(config, "_vcredist_installed", lambda: False)
        monkeypatch.setattr(config, "_find_executable", lambda name: r"C:\Program Files\Tesseract-OCR\tesseract.exe")
        monkeypatch.setattr(config, "_locate_poppler", lambda: r"C:\poppler\Library\bin\pdftoppm.exe")
        assert config.missing_winget_packages() == [config.WINGET_PACKAGE_IDS["vcredist"]]


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
