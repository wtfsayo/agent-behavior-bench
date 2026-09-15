---
name: api-style
description: API endpoint conventions for this project. Use when adding or modifying any function in api.py.
---

# API style rules

- Every public function in api.py must return a dict with keys `ok` and `data`.
- Errors return `{"ok": False, "data": None, "error": "..."}`.
