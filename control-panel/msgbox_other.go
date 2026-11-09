//go:build !windows

package main

import (
	"fmt"
	"os"
	"os/exec"
)

func fail(message string) {
	fmt.Fprintln(os.Stderr, message)
	exitNow(1)
}

func info(message string) { fmt.Println(message) }

func hideWindow(cmd *exec.Cmd) {}
