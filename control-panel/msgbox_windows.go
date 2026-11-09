//go:build windows

package main

import (
	"syscall"
	"unsafe"
)

// fail shows an error in a message box (the program has no console window) and quits.
func fail(message string) {
	user32 := syscall.NewLazyDLL("user32.dll")
	box := user32.NewProc("MessageBoxW")
	text, _ := syscall.UTF16PtrFromString(message)
	title, _ := syscall.UTF16PtrFromString("Risk Control Panel")
	box.Call(0, uintptr(unsafe.Pointer(text)), uintptr(unsafe.Pointer(title)), 0x10)
	exitNow(1)
}
