"""No shell evaluation, auto-install, best-effort batch or HTML acceptance."""
import json
from .runtime import require_actions, run, WordError


class OfficeBackend:
    def invoke(self, command, document, path=None, *, kind=None, props=None, extra=None):
        require_actions()
        args = ["officecli", command, document]
        if path is not None: args.append(path)
        if kind: args.extend(["--type", kind])
        for key, value in (props or {}).items():
            rendered = str(value).lower() if isinstance(value, bool) else str(value)
            args.extend(["--prop", key + "=" + rendered])
        args.extend(extra or [])
        return run(args)

    def flush(self, document):
        self.invoke("save", document)
        self.invoke("close", document)

    def edit(self, document, path, action, kind, props):
        result = self.invoke(action, document, path, kind=kind if action == "add" else None, props=props)
        self.flush(document)
        return result
