// Risk Control Panel: a private app for the bot's owner.
//
// It runs a small web server that only listens on this computer (127.0.0.1), opens it in an app window, and
// passes the owner's actions to the bot's signed /owner API. The secret key stays in this program. The page
// in the window never sees it.
package main

import (
	"crypto/hmac"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"embed"
	"encoding/hex"
	"encoding/json"
	"errors"
	"flag"
	"fmt"
	"io"
	"io/fs"
	"net"
	"net/http"
	"net/url"
	"os"
	"os/exec"
	"path/filepath"
	"regexp"
	"runtime"
	"strconv"
	"strings"
	"sync/atomic"
	"time"
)

//go:embed ui/*
var uiFiles embed.FS

type config struct {
	URL string `json:"url"`
	Key string `json:"key"`
}

type app struct {
	token      string
	port       int
	cfgPath    string
	cfg        config
	client     *http.Client
	lastPing   atomic.Int64
	everPinged atomic.Bool
}

var apiPath = regexp.MustCompile(`^[A-Za-z0-9/_-]{1,80}$`)

func main() {
	port := flag.Int("port", 0, "port to listen on (default: any free port)")
	noBrowser := flag.Bool("no-browser", false, "don't open a window; print the address instead")
	installFlag := flag.Bool("install", false, "install as a Windows app (Start menu, Apps list) and open it")
	uninstallFlag := flag.Bool("uninstall", false, "remove the Windows app and its shortcuts")
	cfgFlag := flag.String("config", "", "path to the settings file (default: next to this program)")
	flag.Parse()

	a := &app{client: &http.Client{Timeout: 60 * time.Second}}
	a.cfgPath = *cfgFlag
	if a.cfgPath == "" {
		exe, err := os.Executable()
		if err != nil {
			fail("Can't find where this program is: " + err.Error())
		}
		a.cfgPath = filepath.Join(filepath.Dir(exe), "RiskPanel.config.json")
	}
	a.load()
	if runInstallFlags(*installFlag, *uninstallFlag, a) {
		return
	}
	buf := make([]byte, 24)
	if _, err := rand.Read(buf); err != nil {
		fail("Can't make a random token: " + err.Error())
	}
	a.token = hex.EncodeToString(buf)

	listener, err := net.Listen("tcp", fmt.Sprintf("127.0.0.1:%d", *port))
	if err != nil {
		fail("Can't start the panel: " + err.Error())
	}
	a.port = listener.Addr().(*net.TCPAddr).Port
	address := fmt.Sprintf("http://127.0.0.1:%d/?t=%s", a.port, a.token)

	a.lastPing.Store(time.Now().Unix())
	go a.watch()
	go func() {
		if err := http.Serve(listener, a.routes()); err != nil {
			fail("The panel stopped: " + err.Error())
		}
	}()

	if *noBrowser {
		fmt.Println(address)
		select {}
	}
	openWindow(address)
	select {}
}

// watch closes the program when its window has been closed for a while.
func (a *app) watch() {
	for {
		time.Sleep(3 * time.Second)
		idle := time.Now().Unix() - a.lastPing.Load()
		if (a.everPinged.Load() && idle > 25) || idle > 120 {
			os.Exit(0)
		}
	}
}

func (a *app) load() {
	data, err := os.ReadFile(a.cfgPath)
	if err == nil {
		_ = json.Unmarshal(data, &a.cfg)
	}
}

func (a *app) save() error {
	data, _ := json.MarshalIndent(a.cfg, "", "  ")
	return os.WriteFile(a.cfgPath, data, 0o600)
}

func (a *app) routes() http.Handler {
	mux := http.NewServeMux()
	sub, _ := fs.Sub(uiFiles, "ui")
	files := http.FileServer(http.FS(sub))
	mux.Handle("/", files)
	mux.HandleFunc("/local/config", a.handleConfig)
	mux.HandleFunc("/local/prefs", a.handlePrefs)
	mux.HandleFunc("/local/install", a.handleInstall)
	mux.HandleFunc("/local/ping", func(w http.ResponseWriter, r *http.Request) {
		a.lastPing.Store(time.Now().Unix())
		a.everPinged.Store(true)
		w.WriteHeader(http.StatusNoContent)
	})
	mux.HandleFunc("/local/quit", func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNoContent)
		go func() { time.Sleep(200 * time.Millisecond); os.Exit(0) }()
	})
	mux.HandleFunc("/api/", a.handleAPI)
	return a.guard(mux)
}

// guard lets only this computer's own window in: right address, right session cookie and, for changes, a header a
// web page on another site can't send.
func (a *app) guard(next http.Handler) http.Handler {
	hosts := map[string]bool{fmt.Sprintf("127.0.0.1:%d", a.port): true, fmt.Sprintf("localhost:%d", a.port): true}
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("Cache-Control", "no-store")
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Content-Security-Policy", "default-src 'self'; style-src 'self'; script-src 'self'; img-src 'self' data:; connect-src 'self'; frame-ancestors 'none'")
		if !hosts[r.Host] {
			http.Error(w, "Not allowed.", http.StatusForbidden)
			return
		}
		if t := r.URL.Query().Get("t"); t != "" {
			if subtle.ConstantTimeCompare([]byte(t), []byte(a.token)) == 1 {
				http.SetCookie(w, &http.Cookie{Name: "rp", Value: a.token, Path: "/", HttpOnly: true, SameSite: http.SameSiteStrictMode})
				http.Redirect(w, r, "/", http.StatusFound)
				return
			}
		}
		cookie, err := r.Cookie("rp")
		if err != nil || subtle.ConstantTimeCompare([]byte(cookie.Value), []byte(a.token)) != 1 {
			http.Error(w, "Open this from the Risk Control Panel program.", http.StatusForbidden)
			return
		}
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			if r.Header.Get("X-Panel") != "1" {
				http.Error(w, "Not allowed.", http.StatusForbidden)
				return
			}
			if origin := r.Header.Get("Origin"); origin != "" && origin != "http://"+r.Host {
				http.Error(w, "Not allowed.", http.StatusForbidden)
				return
			}
		}
		next.ServeHTTP(w, r)
	})
}

func jsonOut(w http.ResponseWriter, status int, v any) {
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_ = json.NewEncoder(w).Encode(v)
}

func (a *app) handleConfig(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		hint := ""
		if len(a.cfg.Key) >= 4 {
			hint = "ending in " + a.cfg.Key[len(a.cfg.Key)-4:]
		}
		jsonOut(w, 200, map[string]any{"configured": a.cfg.URL != "" && a.cfg.Key != "", "url": a.cfg.URL, "keyHint": hint, "path": a.cfgPath})
		return
	}
	var body config
	if err := json.NewDecoder(io.LimitReader(r.Body, 4096)).Decode(&body); err != nil {
		jsonOut(w, 400, map[string]string{"error": "That wasn't valid."})
		return
	}
	clean, err := cleanURL(body.URL)
	if err != nil {
		jsonOut(w, 400, map[string]string{"error": err.Error()})
		return
	}
	key := strings.TrimSpace(body.Key)
	if key == "" {
		key = a.cfg.Key // leaving the key blank keeps the saved one
	}
	if len(key) < 32 {
		jsonOut(w, 400, map[string]string{"error": "The key must be at least 32 characters. It's the OWNER_PANEL_KEY on your bot."})
		return
	}
	trial := config{URL: clean, Key: key}
	status, _, err := a.call(trial, "GET", "status", nil)
	if err != nil {
		jsonOut(w, 502, map[string]string{"error": err.Error()})
		return
	}
	if status == 401 {
		jsonOut(w, 400, map[string]string{"error": "The bot refused that key. Check that it matches OWNER_PANEL_KEY on the bot, and that this computer's clock is right."})
		return
	}
	if status == 503 {
		jsonOut(w, 400, map[string]string{"error": "The bot's owner API is off. Set OWNER_PANEL_KEY on the bot and restart it."})
		return
	}
	if status != 200 {
		jsonOut(w, 400, map[string]string{"error": fmt.Sprintf("The bot answered with status %d.", status)})
		return
	}
	a.cfg = trial
	if err := a.save(); err != nil {
		jsonOut(w, 500, map[string]string{"error": "Connected, but couldn't save the settings: " + err.Error()})
		return
	}
	jsonOut(w, 200, map[string]bool{"ok": true})
}

// prefsPath keeps the look and behaviour choices next to the settings file. They hold no secrets.
func (a *app) prefsPath() string {
	return strings.TrimSuffix(a.cfgPath, filepath.Ext(a.cfgPath)) + ".prefs.json"
}

func (a *app) handlePrefs(w http.ResponseWriter, r *http.Request) {
	if r.Method == http.MethodGet {
		data, err := os.ReadFile(a.prefsPath())
		if err != nil || !json.Valid(data) {
			data = []byte("{}")
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write(data)
		return
	}
	raw, err := io.ReadAll(io.LimitReader(r.Body, 8192))
	var probe map[string]any
	if err != nil || json.Unmarshal(raw, &probe) != nil || probe == nil {
		jsonOut(w, 400, map[string]string{"error": "That wasn't valid."})
		return
	}
	if err := os.WriteFile(a.prefsPath(), raw, 0o600); err != nil {
		jsonOut(w, 500, map[string]string{"error": "Couldn't save: " + err.Error()})
		return
	}
	jsonOut(w, 200, map[string]bool{"ok": true})
}

func cleanURL(raw string) (string, error) {
	raw = strings.TrimSpace(raw)
	if !strings.Contains(raw, "://") {
		raw = "http://" + raw
	}
	u, err := url.Parse(raw)
	if err != nil || u.Host == "" || (u.Scheme != "http" && u.Scheme != "https") {
		return "", errors.New("Type the bot's address, like http://12.34.56.78:25239")
	}
	return u.Scheme + "://" + u.Host, nil
}

func sign(key, method, path, stamp, nonce string, body []byte) string {
	sum := sha256.Sum256(body)
	mac := hmac.New(sha256.New, []byte(key))
	mac.Write([]byte(strings.Join([]string{strings.ToUpper(method), path, stamp, nonce, hex.EncodeToString(sum[:])}, "\n")))
	return hex.EncodeToString(mac.Sum(nil))
}

// call sends one signed request to the bot.
func (a *app) call(c config, method, tail string, body []byte) (int, []byte, error) {
	path := "/owner/" + tail
	nonceBytes := make([]byte, 16)
	if _, err := rand.Read(nonceBytes); err != nil {
		return 0, nil, err
	}
	nonce := hex.EncodeToString(nonceBytes)
	stamp := strconv.FormatInt(time.Now().Unix(), 10)
	req, err := http.NewRequest(method, c.URL+path, strings.NewReader(string(body)))
	if err != nil {
		return 0, nil, err
	}
	req.Header.Set("X-Owner-Time", stamp)
	req.Header.Set("X-Owner-Nonce", nonce)
	req.Header.Set("X-Owner-Sig", sign(c.Key, method, path, stamp, nonce, body))
	req.Header.Set("Content-Type", "application/json")
	resp, err := a.client.Do(req)
	if err != nil {
		return 0, nil, fmt.Errorf("Can't reach the bot at %s. Is it online? (%v)", c.URL, shorten(err))
	}
	defer resp.Body.Close()
	data, _ := io.ReadAll(io.LimitReader(resp.Body, 40<<20))
	return resp.StatusCode, data, nil
}

func shorten(err error) string {
	text := err.Error()
	if len(text) > 120 {
		return text[:120]
	}
	return text
}

func (a *app) handleAPI(w http.ResponseWriter, r *http.Request) {
	if a.cfg.URL == "" || a.cfg.Key == "" {
		jsonOut(w, 400, map[string]string{"error": "Set the bot's address and key first."})
		return
	}
	tail := strings.TrimPrefix(r.URL.Path, "/api/")
	if !apiPath.MatchString(tail) || strings.Contains(tail, "..") {
		jsonOut(w, 400, map[string]string{"error": "Not allowed."})
		return
	}
	body, _ := io.ReadAll(io.LimitReader(r.Body, 64<<10))
	status, data, err := a.call(a.cfg, r.Method, tail, body)
	if err != nil {
		jsonOut(w, 502, map[string]string{"error": err.Error()})
		return
	}
	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(status)
	_, _ = w.Write(data)
}

// openWindow shows the panel as an app window (Edge or Chrome in app mode), or in the default browser.
func openWindow(address string) {
	switch runtime.GOOS {
	case "windows":
		for _, p := range windowsBrowsers() {
			if _, err := os.Stat(p); err == nil {
				if exec.Command(p, "--app="+address, "--window-size=1280,860").Start() == nil {
					return
				}
			}
		}
		_ = exec.Command("rundll32", "url.dll,FileProtocolHandler", address).Start()
	case "darwin":
		_ = exec.Command("open", address).Start()
	default:
		_ = exec.Command("xdg-open", address).Start()
	}
}

func windowsBrowsers() []string {
	var out []string
	for _, base := range []string{os.Getenv("ProgramFiles(x86)"), os.Getenv("ProgramFiles"), os.Getenv("LocalAppData")} {
		if base == "" {
			continue
		}
		out = append(out,
			filepath.Join(base, "Microsoft", "Edge", "Application", "msedge.exe"),
			filepath.Join(base, "Google", "Chrome", "Application", "chrome.exe"))
	}
	return out
}

func exitNow(code int) { os.Exit(code) }
