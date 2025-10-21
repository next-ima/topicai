# security.py
import re
import logging
from typing import List
from datetime import datetime
from bson.objectid import ObjectId
from bson.errors import InvalidId

# Logging for suspicious / rejected inputs
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")

# ---- Configurable rules ----
# Allowed characters for overall keyword string (commas separate topics)
SAFE_KEYWORD_RE = re.compile(r'^[A-Za-z0-9\s,\-\_]{1,200}$')  # whole field
# Allowed characters for individual token (lowercase normalized)
TOKEN_RE = re.compile(r'^[a-z0-9\-\_ ]{1,60}$')  # after lowercasing and trimming

# Limits for AI returned fields (enforce types & lengths before writing to DB)
MAX_GROUP_LEN = 60
MAX_HEADLINE_LEN = 300
MAX_SUMMARY_LEN = 1000
MAX_BODY_LEN = 5000

# Mongo operator signatures and suspicious tokens
MONGO_OPERATOR_SIGNATURES = ["$", "{", "}", "\x00", "$where", "$regex", "function(", "eval(", "__proto__", "$gt", "$lt", "$ne"]

# -------------------------
# Input validation helpers
# -------------------------
def _log_reject(msg: str, payload: str | None = None) -> None:
    logging.warning(f"{msg} payload={payload!r}")

def validate_keyword(raw: str) -> str:
    """
    Validate a single keyword supplied by user (search term).
    Returns normalized string (lowercased trimmed).
    Raises ValueError on invalid input.
    """
    if raw is None:
        raise ValueError("Empty keyword")
    if not isinstance(raw, str):
        raise ValueError("Keyword must be a string")
    s = raw.strip()
    if not s:
        raise ValueError("Empty keyword")
    # We permit spaces and hyphens etc; full string checked against SAFE regex
    if len(s) > 200:
        _log_reject("Rejected keyword (too long)", s)
        raise ValueError("Keyword too long")
    if any(sig in s for sig in MONGO_OPERATOR_SIGNATURES):
        _log_reject("Rejected keyword (suspicious signature)", s)
        raise ValueError("Suspicious characters in keyword")
    if not SAFE_KEYWORD_RE.match(s):
        _log_reject("Rejected keyword (invalid characters)", s)
        raise ValueError("Invalid characters in keyword")
    return s.lower()

def validate_topic_list(raw: str) -> List[str]:
    """
    Accepts a comma-separated string like "ai, robotics" and returns a list
    of normalized tokens: ["ai", "robotics"].
    Raises ValueError for invalid input or if no valid tokens remain.
    """
    if raw is None:
        raise ValueError("Empty topic list")
    if not isinstance(raw, str):
        raise ValueError("Topic list must be a string")
    s = raw.strip()
    if not s:
        raise ValueError("Empty topic list")

    if any(sig in s for sig in MONGO_OPERATOR_SIGNATURES):
        _log_reject("Rejected topic list (suspicious signature)", s)
        raise ValueError("Suspicious characters in topic list")

    if not SAFE_KEYWORD_RE.match(s):
        _log_reject("Rejected topic list (invalid characters)", s)
        raise ValueError("Invalid characters in topic list")

    tokens = [t.strip().lower() for t in s.split(",") if t.strip()]
    clean = []
    for t in tokens:
        if len(t) > 60:
            logging.info("Dropping too-long token from topic list: %r", t)
            continue
        if not TOKEN_RE.match(t):
            logging.info("Dropping token with invalid chars: %r", t)
            continue
        clean.append(t)
    if not clean:
        _log_reject("No valid tokens after normalization", s)
        raise ValueError("No valid topics provided")
    # Optionally deduplicate preserving order
    seen = set()
    out = []
    for t in clean:
        if t not in seen:
            seen.add(t)
            out.append(t)
    return out

def safe_object_id(id_str: str) -> ObjectId:
    """
    Convert id_str to bson.ObjectId reliably; raises ValueError on bad input.
    """
    if not isinstance(id_str, str):
        _log_reject("Invalid ObjectId type", str(id_str))
        raise ValueError("Invalid id format")
    try:
        return ObjectId(id_str)
    except (InvalidId, TypeError) as e:
        _log_reject("Invalid ObjectId format", id_str)
        raise ValueError("Invalid id format") from e

def contains_mongo_operators(data: str) -> bool:
    """
    Quick boolean heuristic to flag suspicious strings containing operator-like tokens.
    """
    if not isinstance(data, str):
        return False
    lower = data.lower()
    return any(sig.lower() in lower for sig in MONGO_OPERATOR_SIGNATURES)

def escape_for_regex(user_input: str) -> str:
    """
    Safely escape user input for use inside a regex query.
    """
    if user_input is None:
        return ""
    return re.escape(user_input.strip())

# -------------------------
# AI output sanitization
# -------------------------
def sanitize_ai_output(group: str, headline: str, summary: str, body: str) -> dict:
    """
    Ensure the AI-produced fields are strings, are within length limits,
    and do not contain suspicious operator sequences.
    Returns a dict with sanitized values.
    If a field is missing or too long, it will be truncated.
    """
    def _safe_str(x, limit):
        if x is None:
            return ""
        if not isinstance(x, str):
            x = str(x)
        # remove embedded null bytes and control characters except newlines/tabs
        x = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f]", "", x)
        if contains_mongo_operators(x):
            logging.info("AI output contained suspicious operator; stripping those parts")
            # neutralize $ and braces to avoid any weirdness (store safe copy)
            x = x.replace("$", "").replace("{", "(").replace("}", ")")
        if len(x) > limit:
            logging.info("Truncating AI output to %d chars", limit)
            x = x[:limit]
        return x.strip()

    return {
        "group": _safe_str(group, MAX_GROUP_LEN),
        "headline": _safe_str(headline, MAX_HEADLINE_LEN),
        "summary": _safe_str(summary, MAX_SUMMARY_LEN),
        "body": _safe_str(body, MAX_BODY_LEN),
        "sanitized_at": datetime.utcnow().isoformat() + "Z"
    }
