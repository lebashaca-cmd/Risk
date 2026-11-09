package main

import (
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"os"
	"os/exec"
	"path/filepath"
	"runtime"
	"strings"
)

// Installing makes the panel a normal Windows app: it lives in %LocalAppData%\Programs, gets a Start menu entry
// (and optionally a desktop icon), and shows up in Settings > Apps so it can be uninstalled. It needs no admin
// rights because everything goes in the current user's own folders and registry keys.
const (
	appName      = "Risk Control Panel"
	exeName      = "RiskPanel.exe"
	appVersion   = "2.0"
	uninstallKey = `HKCU\Software\Microsoft\Windows\CurrentVersion\Uninstall\RiskControlPanel`
	runKey       = `HKCU\Software\Microsoft\Windows\CurrentVersion\Run`
)

// runner runs a program and returns its output. Tests replace it so nothing real is touched.
var runner = func(name string, args []string, env []string) error {
	cmd := exec.Command(name, args...)
	cmd.Env = append(os.Environ(), env...)
	hideWindow(cmd)
	out, err := cmd.CombinedOutput()
	if err != nil {
		return fmt.Errorf("%s failed: %s", filepath.Base(name), strings.TrimSpace(string(out)))
	}
	return nil
}

type places struct {
	installDir string
	startMenu  string
	desktop    string
}

func windowsPlaces() (places, error) {
	local, appdata, profile := os.Getenv("LOCALAPPDATA"), os.Getenv("APPDATA"), os.Getenv("USERPROFILE")
	if local == "" || appdata == "" || profile == "" {
		return places{}, errors.New("Windows didn't tell this program where your user folders are.")
	}
	return places{
		installDir: filepath.Join(local, "Programs", "RiskControlPanel"),
		startMenu:  filepath.Join(appdata, "Microsoft", "Windows", "Start Menu", "Programs", appName+".lnk"),
		desktop:    filepath.Join(profile, "Desktop", appName+".lnk"),
	}, nil
}

func fileExists(path string) bool {
	_, err := os.Stat(path)
	return err == nil
}

func copyFile(from, to string, mode os.FileMode) error {
	in, err := os.Open(from)
	if err != nil {
		return err
	}
	defer in.Close()
	tmp := to + ".new"
	out, err := os.OpenFile(tmp, os.O_CREATE|os.O_WRONLY|os.O_TRUNC, mode)
	if err != nil {
		return err
	}
	if _, err := io.Copy(out, in); err != nil {
		out.Close()
		return err
	}
	if err := out.Close(); err != nil {
		return err
	}
	return os.Rename(tmp, to)
}

func makeShortcut(link, target string) error {
	if err := os.MkdirAll(filepath.Dir(link), 0o755); err != nil {
		return err
	}
	script := `$s=(New-Object -ComObject WScript.Shell).CreateShortcut($env:RP_LNK);$s.TargetPath=$env:RP_TARGET;$s.WorkingDirectory=$env:RP_DIR;$s.Description='Risk Control Panel';$s.IconLocation=$env:RP_TARGET+',0';$s.Save()`
	return runner("powershell.exe", []string{"-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-Command", script},
		[]string{"RP_LNK=" + link, "RP_TARGET=" + target, "RP_DIR=" + filepath.Dir(target)})
}

func regAdd(key, name, kind, value string) error {
	return runner("reg.exe", []string{"add", key, "/v", name, "/t", kind, "/d", value, "/f"}, nil)
}

// installState says what is set up right now.
type installState struct {
	Supported bool   `json:"supported"`
	Installed bool   `json:"installed"`
	Running   bool   `json:"runningInstalled"`
	Path      string `json:"path"`
	Desktop   bool   `json:"desktop"`
	Startup   bool   `json:"startup"`
}

func currentState() installState {
	if runtime.GOOS != "windows" {
		return installState{}
	}
	p, err := windowsPlaces()
	if err != nil {
		return installState{Supported: true}
	}
	target := filepath.Join(p.installDir, exeName)
	self, _ := os.Executable()
	st := installState{Supported: true, Installed: fileExists(target), Path: p.installDir, Desktop: fileExists(p.desktop)}
	st.Running = strings.EqualFold(filepath.Clean(self), filepath.Clean(target))
	st.Startup = runner("reg.exe", []string{"query", runKey, "/v", "RiskControlPanel"}, nil) == nil
	return st
}

// install copies the program and its settings into place and registers it. It returns the installed program's path.
func install(a *app, p places, desktop, startup bool) (string, error) {
	self, err := os.Executable()
	if err != nil {
		return "", err
	}
	if err := os.MkdirAll(p.installDir, 0o755); err != nil {
		return "", err
	}
	target := filepath.Join(p.installDir, exeName)
	if !strings.EqualFold(filepath.Clean(self), filepath.Clean(target)) {
		if err := copyFile(self, target, 0o755); err != nil {
			return "", fmt.Errorf("couldn't copy the program: %w", err)
		}
	}
	// Bring the saved address, key and look along so nothing has to be entered again.
	if a != nil && a.cfg.URL != "" {
		data, _ := json.MarshalIndent(a.cfg, "", "  ")
		if err := os.WriteFile(filepath.Join(p.installDir, "RiskPanel.config.json"), data, 0o600); err != nil {
			return "", err
		}
		if prefs, err := os.ReadFile(a.prefsPath()); err == nil {
			_ = os.WriteFile(filepath.Join(p.installDir, "RiskPanel.prefs.json"), prefs, 0o600)
		}
	}
	if err := makeShortcut(p.startMenu, target); err != nil {
		return "", err
	}
	if desktop {
		if err := makeShortcut(p.desktop, target); err != nil {
			return "", err
		}
	}
	steps := [][]string{
		{"DisplayName", "REG_SZ", appName}, {"DisplayVersion", "REG_SZ", appVersion}, {"Publisher", "REG_SZ", "Risk"},
		{"DisplayIcon", "REG_SZ", target}, {"InstallLocation", "REG_SZ", p.installDir},
		{"UninstallString", "REG_SZ", `"` + target + `" --uninstall`}, {"NoModify", "REG_DWORD", "1"}, {"NoRepair", "REG_DWORD", "1"},
	}
	for _, s := range steps {
		if err := regAdd(uninstallKey, s[0], s[1], s[2]); err != nil {
			return "", err
		}
	}
	if err := setStartup(target, startup); err != nil {
		return "", err
	}
	return target, nil
}

func setStartup(target string, on bool) error {
	if on {
		return regAdd(runKey, "RiskControlPanel", "REG_SZ", `"`+target+`"`)
	}
	// Deleting a value that isn't there is fine.
	_ = runner("reg.exe", []string{"delete", runKey, "/v", "RiskControlPanel", "/f"}, nil)
	return nil
}

func setDesktop(target string, p places, on bool) error {
	if on {
		return makeShortcut(p.desktop, target)
	}
	if err := os.Remove(p.desktop); err != nil && !os.IsNotExist(err) {
		return err
	}
	return nil
}

// uninstall removes the shortcuts, registry entries and the program folder (after this process has quit).
func uninstall(p places) error {
	for _, link := range []string{p.startMenu, p.desktop} {
		if err := os.Remove(link); err != nil && !os.IsNotExist(err) {
			return err
		}
	}
	_ = runner("reg.exe", []string{"delete", uninstallKey, "/f"}, nil)
	_ = setStartup("", false)
	if runtime.GOOS == "windows" {
		// The running program can't delete itself, so a small script does it a few seconds from now.
		bat := filepath.Join(os.TempDir(), "risk-panel-uninstall.bat")
		script := "@echo off\r\nping 127.0.0.1 -n 4 >nul\r\nrmdir /s /q \"" + p.installDir + "\"\r\ndel \"%~f0\"\r\n"
		if err := os.WriteFile(bat, []byte(script), 0o600); err != nil {
			return err
		}
		cmd := exec.Command("cmd.exe", "/c", bat)
		hideWindow(cmd)
		return cmd.Start()
	}
	return os.RemoveAll(p.installDir)
}

func (a *app) handleInstall(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		jsonOut(w, 200, currentState())
		return
	}
	if runtime.GOOS != "windows" {
		jsonOut(w, 400, map[string]string{"error": "Installing as a Windows app only works on Windows."})
		return
	}
	var body struct {
		Action  string `json:"action"`
		Desktop bool   `json:"desktop"`
		Startup bool   `json:"startup"`
	}
	if err := json.NewDecoder(io.LimitReader(r.Body, 1024)).Decode(&body); err != nil {
		jsonOut(w, 400, map[string]string{"error": "That wasn't valid."})
		return
	}
	p, err := windowsPlaces()
	if err != nil {
		jsonOut(w, 500, map[string]string{"error": err.Error()})
		return
	}
	target := filepath.Join(p.installDir, exeName)
	fail := func(err error) { jsonOut(w, 500, map[string]string{"error": err.Error()}) }
	switch body.Action {
	case "install":
		target, err := install(a, p, body.Desktop, body.Startup)
		if err != nil {
			fail(err)
			return
		}
		jsonOut(w, 200, map[string]any{"ok": true, "message": "Installed. The panel is reopening from its new home."})
		// Open the installed copy and close this one, unless this already is the installed copy.
		self, _ := os.Executable()
		if !strings.EqualFold(filepath.Clean(self), filepath.Clean(target)) {
			go func() { _ = exec.Command(target).Start(); exitNow(0) }()
		}
	case "desktop-on", "desktop-off":
		if !fileExists(target) {
			jsonOut(w, 400, map[string]string{"error": "Install the app first."})
			return
		}
		if err := setDesktop(target, p, body.Action == "desktop-on"); err != nil {
			fail(err)
			return
		}
		jsonOut(w, 200, map[string]bool{"ok": true})
	case "startup-on", "startup-off":
		if !fileExists(target) {
			jsonOut(w, 400, map[string]string{"error": "Install the app first."})
			return
		}
		if err := setStartup(target, body.Action == "startup-on"); err != nil {
			fail(err)
			return
		}
		jsonOut(w, 200, map[string]bool{"ok": true})
	case "uninstall":
		if err := uninstall(p); err != nil {
			fail(err)
			return
		}
		jsonOut(w, 200, map[string]any{"ok": true, "message": "Uninstalled. The panel is closing."})
		go func() { exitNow(0) }()
	default:
		jsonOut(w, 400, map[string]string{"error": "Unknown action."})
	}
}

// runInstallFlags handles --install and --uninstall from the command line (Windows' Apps list runs --uninstall).
func runInstallFlags(install_, uninstall_ bool, a *app) bool {
	if !install_ && !uninstall_ {
		return false
	}
	if runtime.GOOS != "windows" {
		fmt.Fprintln(os.Stderr, "Installing as a Windows app only works on Windows.")
		exitNow(1)
	}
	p, err := windowsPlaces()
	if err != nil {
		fail(err.Error())
	}
	if uninstall_ {
		if err := uninstall(p); err != nil {
			fail("Couldn't uninstall: " + err.Error())
		}
		info(appName + " was removed.")
		return true
	}
	target, err := install(a, p, false, false)
	if err != nil {
		fail("Couldn't install: " + err.Error())
	}
	_ = exec.Command(target).Start()
	return true
}
