//go:build !windows

package main

import (
	"fmt"
	"os"
)

func fail(message string) {
	fmt.Fprintln(os.Stderr, message)
	exitNow(1)
}
