#!/usr/bin/env python3
"""TypeSafe (Jev) API client for the every-frame pass; Python 3.9+, no dependencies.

Bring your own key: set TYPESAFE_API_KEY in the environment, or put TYPESAFE_API_KEY=... in the
.env file in the skill folder. Create a key at https://console.typesafe.ai.

HTTP contract: https://docs.typesafe.ai/api and /models (checked 2026-09-19; image assets
and box questions added 2026-10-27). Image assets may be read from absolute local PNG/JPEG
paths named in the request; nothing else on disk is read.
MCP: https://modelcontextprotocol.io/specification/2025-06-18.
No automatic disk logging, arbitrary URLs, shell execution, or key disclosure.
"""
import argparse
import base64
from email.utils import parsedate_to_datetime
import json
import os
from pathlib import Path
import stat
import sys
import time
import urllib.error
import urllib.request

DEFAULT_MODEL = "jev-1.13.0"
DEFAULT_IMAGE_MODEL = "jev-preview"  # docs: image assets need a vision-language model (checked 2026-10-27)
SECRET_PATH = Path(__file__).resolve().parent.parent / ".env"  # the skill folder's .env
MAX_REQUEST_BYTES = 262144
MAX_IMAGE_REQUEST_BYTES = 16777216
MAX_IMAGE_BYTES = 5242880
MAX_ASSETS = 20
MAX_RESPONSE_BYTES = 2097152
MAX_QUESTIONS = 100
TIMEOUT_SECONDS = 20
IMAGE_TIMEOUT_SECONDS = 90
QUESTION_TYPES = ("choice", "score", "noul", "box")
IMAGE_HEADER = "TypeSafe-Danger-Zone-Images"
MAX_ATTEMPTS = 3
PROTOCOL = "2025-06-18"


class SafeError(Exception):
    """Only constant, credential-free messages may be used here."""


def secret_path():
    return Path(os.environ.get("TYPESAFE_SECRET_FILE", str(SECRET_PATH))).expanduser()


def clean_key(value):
    value = value.strip()
    placeholders = ("your_", "your-", "paste", "replace", "changeme", "<", "placeholder")
    if not value or value.lower().startswith(placeholders):
        raise SafeError("TypeSafe key is not configured. Set TYPESAFE_API_KEY in the environment or in the skill folder's .env file.")
    if len(value) > 4096 or any(ord(c) < 33 or ord(c) > 126 for c in value):
        raise SafeError("TypeSafe key has an invalid format; use the API key only.")
    return value


def read_key():
    # Environment takes precedence, including an explicitly empty value.
    if "TYPESAFE_API_KEY" in os.environ:
        return clean_key(os.environ["TYPESAFE_API_KEY"])
    path = secret_path()
    try:
        flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0)
        fd = os.open(path, flags)
        with os.fdopen(fd, "r", encoding="utf-8") as handle:
            info = os.fstat(handle.fileno())
            if not stat.S_ISREG(info.st_mode):
                raise SafeError("TypeSafe secret must be a regular file.")
            data = handle.read(16385)
            if len(data) > 16384:
                raise SafeError("TypeSafe secret file is too large.")
    except (OSError, UnicodeError):
        raise SafeError("TypeSafe secret file is missing, unreadable, or is a symlink.") from None
    values = []
    for line in data.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        name, sep, value = line.partition("=")
        if sep and name.strip() == "TYPESAFE_API_KEY":
            value = value.strip()
            if len(value) >= 2 and value[0] == value[-1] and value[0] in "\"'":
                value = value[1:-1]
            values.append(value)
    if len(values) != 1:
        raise SafeError("Set exactly one TYPESAFE_API_KEY in the environment or the skill folder's .env file.")
    return clean_key(values[0])


def status():
    try:
        read_key()
        configured = True
    except SafeError:
        configured = False
    return {"configured": configured, "secret_file": str(secret_path())}


def encode_json(value):
    try:
        return json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")).encode("utf-8")
    except (ValueError, TypeError, UnicodeError, RecursionError):
        raise SafeError("Input must be valid finite JSON.") from None


def parse_json(data):
    try:
        def invalid_constant(_):
            raise ValueError()
        return json.loads(data, parse_constant=invalid_constant)
    except (ValueError, UnicodeError, RecursionError):
        raise SafeError("Invalid JSON input or response.") from None


def _placeholder_ok(name):
    return isinstance(name, str) and 1 <= len(name) <= 64 and all(c.isalnum() or c in "_-" for c in name)


def _image_format(data):
    if data.startswith(b"\x89PNG\r\n\x1a\n"):
        return "png"
    if data.startswith(b"\xff\xd8\xff"):
        return "jpeg"
    return None


def load_image_file(path_text):
    """Read one local PNG/JPEG for an image asset. No symlinks, no other file types."""
    if not isinstance(path_text, str) or not path_text.startswith("/") or len(path_text) > 4096:
        raise SafeError("Image asset path must be an absolute path.")
    if Path(path_text).suffix.lower() not in (".png", ".jpg", ".jpeg"):
        raise SafeError("Image asset path must end in .png, .jpg or .jpeg.")
    try:
        fd = os.open(path_text, os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0) | getattr(os, "O_NONBLOCK", 0))
        with os.fdopen(fd, "rb") as handle:
            if not stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                raise SafeError("Image asset must be a regular file.")
            data = handle.read(MAX_IMAGE_BYTES + 1)
    except OSError:
        raise SafeError("Image asset file is missing, unreadable, or is a symlink.") from None
    if len(data) > MAX_IMAGE_BYTES:
        raise SafeError("Image asset exceeds the local 5 MiB limit; downscale it.")
    fmt = _image_format(data)
    if fmt is None:
        raise SafeError("Image asset content is not PNG or JPEG.")
    return {"type": "image", "format": fmt, "data_base64": base64.b64encode(data).decode("ascii")}


def resolve_assets(assets, referenced_text):
    if not isinstance(assets, dict) or not 1 <= len(assets) <= MAX_ASSETS:
        raise SafeError("assets must contain between 1 and 20 named images.")
    resolved = {}
    for name, asset in assets.items():
        if not _placeholder_ok(name):
            raise SafeError("Asset placeholders must be 1-64 letters, digits, _ or -.")
        if name not in referenced_text:
            raise SafeError("Every asset placeholder must appear in state, instructions or criteria.")
        if not isinstance(asset, dict):
            raise SafeError("Each asset must be an object.")
        if set(asset) == {"path"}:
            resolved[name] = load_image_file(asset["path"])
        elif set(asset) <= {"type", "format", "data_base64"} and asset.get("type") == "image":
            if asset.get("format") not in ("png", "jpg", "jpeg") or not isinstance(asset.get("data_base64"), str):
                raise SafeError("Inline image assets need format png/jpg/jpeg and data_base64.")
            try:
                raw = base64.b64decode(asset["data_base64"], validate=True)
            except ValueError:
                raise SafeError("Inline image data_base64 is not valid base64.") from None
            if len(raw) > MAX_IMAGE_BYTES or _image_format(raw) is None:
                raise SafeError("Inline image must be PNG or JPEG under 5 MiB.")
            resolved[name] = dict(asset)
        else:
            raise SafeError("Each asset must be {path} or {type: image, format, data_base64}.")
    return resolved


def validate_request(request):
    if not isinstance(request, dict):
        raise SafeError("Evaluation request must be a JSON object.")
    if set(request) - {"state", "questions", "model", "assets"}:
        raise SafeError("Evaluation accepts only state, questions, optional model and optional assets.")
    if not isinstance(request.get("state"), (str, dict, list)):
        raise SafeError("state must be text, an object, or an array.")
    questions = request.get("questions")
    if not isinstance(questions, dict) or not 1 <= len(questions) <= MAX_QUESTIONS:
        raise SafeError("questions must contain between 1 and 100 named questions.")
    for name, question in questions.items():
        if not isinstance(name, str) or not name or not isinstance(question, dict):
            raise SafeError("Each question must have a nonempty name and an object value.")
        kind = question.get("type")
        if kind not in QUESTION_TYPES:
            raise SafeError("Question type must be choice, score, noul, or box.")
        if not isinstance(question.get("instructions"), (str, dict, list)):
            raise SafeError("Question instructions must be text, an object, or an array.")
        criteria = question.get("criteria")
        if kind == "choice" and (not isinstance(criteria, dict) or len(criteria) < 2):
            raise SafeError("Choice criteria must be an object with at least two options.")
        if kind == "score" and (not isinstance(criteria, list) or len(criteria) < 2):
            raise SafeError("Score criteria must be an array with at least two levels.")
        if kind == "noul" and criteria is not None and not isinstance(criteria, dict):
            raise SafeError("Noul criteria, when present, must be an object.")
        if kind == "box" and criteria is not None:
            raise SafeError("Box questions take no criteria.")
    has_box = any(q.get("type") == "box" for q in questions.values())
    if has_box and "assets" not in request:
        raise SafeError("Box questions need at least one image asset.")
    images = "assets" in request
    model = request.get("model", DEFAULT_IMAGE_MODEL if images else DEFAULT_MODEL)
    if not isinstance(model, str) or not model.strip() or len(model) > 100:
        raise SafeError("model must be a nonempty model name of at most 100 characters.")
    result = dict(request, model=model)
    if len(encode_json(result)) > MAX_REQUEST_BYTES:
        raise SafeError("Request exceeds the local 256 KiB limit; split the work into smaller requests.")
    if images:
        referenced = encode_json({"s": request["state"], "q": questions}).decode("utf-8")
        result["assets"] = resolve_assets(request["assets"], referenced)
        if len(encode_json(result)) > MAX_IMAGE_REQUEST_BYTES:
            raise SafeError("Request with images exceeds the local 16 MiB limit; use fewer or smaller images.")
    return result


class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


def api_call(endpoint, payload=None):
    if endpoint not in ("models", "systemone"):
        raise SafeError("Unsupported API operation.")
    key = read_key()
    body = encode_json(payload) if payload is not None else None
    images = isinstance(payload, dict) and ("assets" in payload or any(
        isinstance(q, dict) and q.get("type") == "box" for q in (payload.get("questions") or {}).values()))
    headers = {"Authorization": "Bearer " + key, "Content-Type": "application/json", "Accept": "application/json"}
    if images:
        headers[IMAGE_HEADER] = "true"
    opener = urllib.request.build_opener(urllib.request.ProxyHandler({}), NoRedirect())
    request = urllib.request.Request(
        "https://api.typesafe.ai/v1/" + endpoint,
        data=body,
        headers=headers,
        method="GET" if payload is None else "POST",
    )
    timeout = IMAGE_TIMEOUT_SECONDS if images else TIMEOUT_SECONDS
    for attempt in range(MAX_ATTEMPTS):
        try:
            with opener.open(request, timeout=timeout) as response:
                raw = response.read(MAX_RESPONSE_BYTES + 1)
                if len(raw) > MAX_RESPONSE_BYTES:
                    raise SafeError("TypeSafe response exceeded the local size limit.")
                value = parse_json(raw)
                if not isinstance(value, dict):
                    raise SafeError("TypeSafe returned an unexpected response format.")
                # Do not expose credentials even if a service response echoes one.
                def redact(item):
                    if isinstance(item, str):
                        return item.replace(key, "[REDACTED]")
                    if isinstance(item, dict):
                        return {redact(k): redact(v) for k, v in item.items()}
                    if isinstance(item, list):
                        return [redact(v) for v in item]
                    return item
                return redact(value)
        except urllib.error.HTTPError as error:
            code = error.code
            retry_after = error.headers.get("Retry-After", "") if error.headers else ""
            error.close()
            if code in (429, 529) and attempt < MAX_ATTEMPTS - 1:
                delay = min(2 ** attempt, 5)
                try:
                    requested_delay = float(retry_after)
                except ValueError:
                    try:
                        requested_delay = parsedate_to_datetime(retry_after).timestamp() - time.time()
                    except (TypeError, ValueError, OverflowError):
                        requested_delay = 0
                if requested_delay > 5:
                    raise SafeError("TypeSafe requested a longer retry delay; try again later.")
                if requested_delay >= 0:
                    delay = max(delay, requested_delay)
                time.sleep(delay)
                continue
            if code in (401, 403):
                raise SafeError("TypeSafe rejected authentication or access. Check the API key and account permissions.") from None
            if code in (429, 529):
                raise SafeError("TypeSafe is rate limited or overloaded after bounded retries; try again later.") from None
            if 300 <= code < 400:
                raise SafeError("TypeSafe returned a redirect; blocked to protect the API key.") from None
            raise SafeError("TypeSafe request failed with HTTP status " + str(code) + ".") from None
        except (urllib.error.URLError, OSError, TimeoutError):
            raise SafeError("TypeSafe connection failed or timed out. No automatic retry was made for an uncertain request.") from None


def evaluate(request):
    return api_call("systemone", validate_request(request))


def smoke_test():
    return evaluate({"state": "Fictional test: I cannot sign in to my practice exam account.", "questions": {
        "department": {"type": "choice", "instructions": "Which team should handle this request?", "criteria": {
            "access_support": "Trouble signing in or accessing an account",
            "billing": "Payment, invoice, or refund requests",
            "unclear": "There is insufficient information to choose a team"}}}})


REQUEST_SCHEMA = {"type": "object", "properties": {
    "state": {"type": ["string", "object", "array"]},
    "questions": {"type": "object", "minProperties": 1, "maxProperties": MAX_QUESTIONS,
                  "additionalProperties": {"type": "object", "properties": {
                      "type": {"enum": list(QUESTION_TYPES)},
                      "instructions": {"type": ["string", "object", "array"]},
                      "criteria": {"type": ["object", "array"]}}, "required": ["type", "instructions"]}},
    "model": {"type": "string", "description": "Defaults to " + DEFAULT_MODEL + ", or " + DEFAULT_IMAGE_MODEL + " when assets are given."},
    "assets": {"type": "object", "maxProperties": MAX_ASSETS,
               "description": "Optional images keyed by placeholder. Each placeholder must appear in state, instructions or criteria. Value: {\"path\": \"/absolute/file.jpg\"} (PNG/JPEG on this Mac, at most 5 MiB) or {\"type\": \"image\", \"format\": \"jpeg\", \"data_base64\": \"...\"}.",
               "additionalProperties": {"type": "object"}}},
    "required": ["state", "questions"], "additionalProperties": False}
EMPTY_SCHEMA = {"type": "object", "properties": {}, "additionalProperties": False}
TOOLS = [
    {"name": "typesafe_status", "description": "Check whether the local TypeSafe key is configured. Does not contact TypeSafe or return the key.", "inputSchema": EMPTY_SCHEMA},
    {"name": "typesafe_models", "description": "List models available to this TypeSafe account. Contacts api.typesafe.ai using the locally stored key.", "inputSchema": EMPTY_SCHEMA},
    {"name": "typesafe_evaluate", "description": "Send supplied state and typed questions to TypeSafe Jev for evaluation. This transmits the supplied content and consumes API credit. Use narrow questions and inspect uncertainty; answers are not verified facts. At most 100 questions and 256 KiB per call (images read from local paths may add up to 16 MiB). Question types: choice, score, noul, and box (locates something in an image; needs assets). Image requests send the experimental image header and default to jev-preview; otherwise defaults to jev-1.13.0.", "inputSchema": REQUEST_SCHEMA},
    {"name": "typesafe_smoke_test", "description": "Make one small fictional support classification request to verify API access. Consumes a small amount of TypeSafe API credit.", "inputSchema": EMPTY_SCHEMA},
]
for _tool in TOOLS:
    _tool["annotations"] = {"readOnlyHint": True, "destructiveHint": False,
                            "idempotentHint": _tool["name"] in ("typesafe_status", "typesafe_models"),
                            "openWorldHint": _tool["name"] != "typesafe_status"}


def tool_call(name, arguments):
    if not isinstance(arguments, dict):
        raise SafeError("Tool arguments must be an object.")
    if name != "typesafe_evaluate" and arguments:
        raise SafeError("This tool accepts no arguments.")
    if name == "typesafe_status":
        return status()
    if name == "typesafe_models":
        return api_call("models")
    if name == "typesafe_evaluate":
        return evaluate(arguments)
    if name == "typesafe_smoke_test":
        return smoke_test()
    raise SafeError("Unknown TypeSafe tool.")


def serve_mcp(input_stream=None, output_stream=None):
    source = input_stream or sys.stdin.buffer
    destination = output_stream or sys.stdout
    initialized = False

    def send(value):
        destination.write(encode_json(value).decode("utf-8") + "\n")
        destination.flush()

    while True:
        line = source.readline(MAX_REQUEST_BYTES + 8193)
        if not line:
            return
        if len(line) > MAX_REQUEST_BYTES + 8192:
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "MCP message exceeds local size limit."}})
            return
        try:
            message = parse_json(line)
        except SafeError:
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": "Parse error"}})
            continue
        if not isinstance(message, dict) or message.get("jsonrpc") != "2.0" or not isinstance(message.get("method"), str):
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request"}})
            continue
        # Notifications have no reply, including initialized/cancelled.
        if "id" not in message:
            continue
        ident = message["id"]
        if not isinstance(ident, (str, int)) or isinstance(ident, bool):
            send({"jsonrpc": "2.0", "id": None, "error": {"code": -32600, "message": "Invalid request id"}})
            continue
        reply = {"jsonrpc": "2.0", "id": ident}
        method = message["method"]
        params = message.get("params", {})
        if not isinstance(params, dict):
            reply["error"] = {"code": -32602, "message": "Invalid params"}
        elif method == "initialize":
            initialized = True
            version = params.get("protocolVersion")
            reply["result"] = {"protocolVersion": version if version in ("2024-11-05", "2025-03-26", PROTOCOL) else PROTOCOL,
                               "capabilities": {"tools": {}}, "serverInfo": {"name": "typesafe-local", "version": "1.1.0"}}
        elif method == "ping":
            reply["result"] = {}
        elif not initialized:
            reply["error"] = {"code": -32000, "message": "Initialize the server first"}
        elif method == "tools/list":
            reply["result"] = {"tools": TOOLS}
        elif method == "tools/call":
            if not isinstance(params.get("name"), str) or params["name"] not in {tool["name"] for tool in TOOLS}:
                reply["error"] = {"code": -32602, "message": "Unknown tool"}
            else:
                try:
                    result = tool_call(params["name"], params.get("arguments", {}))
                    reply["result"] = {"content": [{"type": "text", "text": encode_json(result).decode("utf-8")}], "isError": False}
                except SafeError as error:
                    reply["result"] = {"content": [{"type": "text", "text": str(error)}], "isError": True}
                except Exception:
                    reply["result"] = {"content": [{"type": "text", "text": "Local TypeSafe adapter failed; no diagnostic payload was logged."}], "isError": True}
        else:
            reply["error"] = {"code": -32601, "message": "Method not found"}
        send(reply)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("status", "models", "evaluate", "smoke-test", "mcp"))
    parser.add_argument("--request", default="-", help="Evaluation JSON file; - reads stdin")
    parser.add_argument("--output", help="Explicit result JSON path; otherwise stdout")
    args = parser.parse_args(argv)
    try:
        if args.command == "mcp":
            if args.output or args.request != "-":
                raise SafeError("MCP mode accepts no request or output paths.")
            serve_mcp()
            return 0
        if args.command == "status":
            result = status()
        elif args.command == "models":
            result = api_call("models")
        elif args.command == "smoke-test":
            result = smoke_test()
        else:
            if args.request == "-":
                raw = sys.stdin.buffer.read(MAX_REQUEST_BYTES + 1)
            else:
                with open(args.request, "rb") as handle:
                    raw = handle.read(MAX_REQUEST_BYTES + 1)
            if len(raw) > MAX_REQUEST_BYTES:
                raise SafeError("Request file exceeds the local 256 KiB limit.")
            result = evaluate(parse_json(raw))
        output = json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
        if args.output:
            # Never overwrite files, and create potentially sensitive results privately.
            fd = os.open(args.output, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            with os.fdopen(fd, "w", encoding="utf-8") as handle:
                handle.write(output)
        else:
            sys.stdout.write(output)
        return 0
    except SafeError as error:
        sys.stderr.write(str(error) + "\n")
        return 2
    except (OSError, ValueError, UnicodeError):
        sys.stderr.write("Local file or data operation failed; no secret or payload was logged.\n")
        return 2


if __name__ == "__main__":
    sys.exit(main())
