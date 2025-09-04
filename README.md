# Watergate 🎧

Wiretaps for things.

# App

```shell
uv run main.py
```

### Service

To make sure watergate service keeps running in the background, copy `watergate.service` to `~/.config/systemd/user/` and then `systemctl restart watergate`. To see logs use `journalctl -e --user-unit=watergate`.

# Client

### Send data via terminal

```shell
echo '{ "event_type": "module_load", "user_id": "test", "props": {"foo": "bar" }}' | nc -N $WATERGATE_HOST $WATERGATE_PORT 
```

### Using python

```python
import socket
import json

payload = {"event_type":"pytest","user_id":"test","props":{"python":"test"}} 
data = json.dumps(payload)
sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
try:
    sock.connect((WATERGATE_HOST, WATERGATE_PORT))
    sock.sendall(bytes(data,encoding="utf-8"))
    sock.shutdown(socket.SHUT_WR)
    received = sock.recv(1024)
    print(received.decode("utf-8"))
finally:
    sock.close()
```

### Using Nextflow

```groovy
import groovy.json.JsonOutput
import java.net.Socket

workflow.onComplete = {

    def workflowSummary = [
            runName           : workflow.runName,
            start             : workflow.start.format("yyyy-MM-dd HH:mm:ss"),
            complete          : workflow.complete.format("yyyy-MM-dd HH:mm:ss"),
            succeeded         : workflow.success,
            repository        : workflow.repository.toString(),
            scriptFile        : workflow.scriptFile.toString(),
            duration          : workflow.duration.toString(),
            exitStatus        : workflow.exitStatus,
            errorMessage      : workflow.errorMessage ?: "",
            commitId          : workflow.commitId,
            revision          : workflow.revision,
    ]

    def payload = JsonOutput.toJson([event_type : "nextflow_workflow", user_id : workflow.userName, props: workflowSummary])
    def host = WATERGATE_HOST
    def port = WATERGATE_PORT

    try {    
      new Socket(host, port).withCloseable { socket ->
          socket.outputStream.write(payload.getBytes("UTF-8"))
          socket.outputStream.flush()
          socket.shutdownOutput()
      }
    } catch(Exception ex) {
      //silently fail...
    }
}
```


### tcl


```tcl
namespace eval telemetry {
  proc send {mod} {
    set user  [expr {[info exists ::env(USER)] ? $::env(USER) : "unknown"}]
    set json [format {{ "event_type": "module_load", "user_id": "%s", "props": { "module": "%s" } }} $user $mod]
    catch { exec sh -c "printf '%s\n' '$json' | nc -N $WATERGATE_HOST $WATERGATE_PORT" > /dev/null 2>@1 & } _
  }
}

# use
telemetry::send [module-info name]
```