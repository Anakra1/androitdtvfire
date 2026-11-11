// CBR's C ABI for TorrServer's embedded mode. GPL-3.0-or-later.
package main

/*
#include <stdint.h>
*/
import "C"

import (
    "fmt"
    "os"
    "strconv"
    "sync"
    "unsafe"

    "server"
    "server/log"
    "server/settings"
)

var engineMu sync.Mutex
var running bool

func report(buffer *C.char, capacity C.int, message string) C.int {
    if buffer != nil && capacity > 0 && capacity <= 65536 {
        out := unsafe.Slice((*byte)(unsafe.Pointer(buffer)), int(capacity))
        n := copy(out[:len(out)-1], message)
        out[n] = 0
    }
    return 1
}

//export CBRStart
func CBRStart(port C.int, directory *C.char, errorBuffer *C.char, capacity C.int) C.int {
    engineMu.Lock()
    defer engineMu.Unlock()
    if running { return 0 }
    if port < 1024 || port > 65535 || directory == nil {
        return report(errorBuffer, capacity, "Invalid CBR engine configuration")
    }
    path := C.GoString(directory)
    if err := os.MkdirAll(path, 0700); err != nil {
        return report(errorBuffer, capacity, err.Error())
    }
    settings.Embedded = true
    settings.Path = path
    log.Init(os.DevNull, os.DevNull)
    settings.Args = &settings.ExecArgs{
        Port: strconv.Itoa(int(port)), IPs: []string{"127.0.0.1"},
        Path: path, LogPath: os.DevNull, WebLogPath: os.DevNull,
        RDB: false, SearchWA: false,
    }
    if err := server.Start(); err != nil {
        return report(errorBuffer, capacity, fmt.Sprintf("CBR engine: %v", err))
    }
    running = true
    go func() {
        server.WaitServer()
        engineMu.Lock()
        running = false
        engineMu.Unlock()
    }()
    return 0
}

//export CBRStop
func CBRStop() {
    engineMu.Lock()
    active := running
    engineMu.Unlock()
    if active { server.Stop() }
}

func main() {}
