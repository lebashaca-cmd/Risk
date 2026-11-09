package main

import (
	"os"
	"path/filepath"
	"strings"
	"testing"
)

type call struct {
	name string
	args []string
	env  []string
}

func TestInstallAndUninstall(t *testing.T) {
	root := t.TempDir()
	t.Setenv("LOCALAPPDATA", filepath.Join(root, "Local"))
	t.Setenv("APPDATA", filepath.Join(root, "Roaming"))
	t.Setenv("USERPROFILE", filepath.Join(root, "User"))
	var calls []call
	old := runner
	runner = func(name string, args []string, env []string) error {
		calls = append(calls, call{name, args, env})
		return nil
	}
	defer func() { runner = old }()

	p, err := windowsPlaces()
	if err != nil {
		t.Fatal(err)
	}
	cfg := filepath.Join(root, "src", "RiskPanel.config.json")
	_ = os.MkdirAll(filepath.Dir(cfg), 0o755)
	a := &app{cfgPath: cfg, cfg: config{URL: "http://1.2.3.4:25000", Key: strings.Repeat("k", 40)}}
	_ = os.WriteFile(a.prefsPath(), []byte(`{"theme":"glass"}`), 0o600)

	target, err := install(a, p, true, true)
	if err != nil {
		t.Fatal(err)
	}
	if target != filepath.Join(p.installDir, exeName) || !fileExists(target) {
		t.Fatalf("program not copied: %s", target)
	}
	if data, _ := os.ReadFile(filepath.Join(p.installDir, "RiskPanel.config.json")); !strings.Contains(string(data), "1.2.3.4") {
		t.Fatal("config not carried over")
	}
	if data, _ := os.ReadFile(filepath.Join(p.installDir, "RiskPanel.prefs.json")); !strings.Contains(string(data), "glass") {
		t.Fatal("look not carried over")
	}
	var shortcuts, regs int
	var uninstallString, run string
	for _, c := range calls {
		if c.name == "powershell.exe" {
			shortcuts++
			joined := strings.Join(c.env, "|")
			if !strings.Contains(joined, "RP_TARGET="+target) {
				t.Fatalf("shortcut target wrong: %v", c.env)
			}
		}
		if c.name == "reg.exe" {
			regs++
			if c.args[1] == uninstallKey && c.args[3] == "UninstallString" {
				uninstallString = c.args[7]
			}
			if c.args[1] == runKey {
				run = c.args[7]
			}
		}
	}
	if shortcuts != 2 {
		t.Fatalf("want start menu and desktop shortcuts, got %d", shortcuts)
	}
	if uninstallString != `"`+target+`" --uninstall` {
		t.Fatalf("bad uninstall string: %s", uninstallString)
	}
	if run != `"`+target+`"` {
		t.Fatalf("startup entry missing: %q", run)
	}
	if regs < 9 {
		t.Fatalf("registry writes missing: %d", regs)
	}

	// shortcuts are made by PowerShell, so make the files the way it would and check uninstall removes them
	for _, f := range []string{p.startMenu, p.desktop} {
		_ = os.MkdirAll(filepath.Dir(f), 0o755)
		_ = os.WriteFile(f, []byte("x"), 0o644)
	}
	calls = nil
	if err := uninstall(p); err != nil {
		t.Fatal(err)
	}
	if fileExists(p.startMenu) || fileExists(p.desktop) || fileExists(p.installDir) {
		t.Fatal("uninstall left files behind")
	}
	var deletedKey, deletedRun bool
	for _, c := range calls {
		if c.name == "reg.exe" && c.args[0] == "delete" && c.args[1] == uninstallKey {
			deletedKey = true
		}
		if c.name == "reg.exe" && c.args[0] == "delete" && c.args[1] == runKey {
			deletedRun = true
		}
	}
	if !deletedKey || !deletedRun {
		t.Fatal("registry entries not removed")
	}
}
