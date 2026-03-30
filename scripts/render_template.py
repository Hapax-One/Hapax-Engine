#!/usr/bin/env python3
from __future__ import annotations

import os
import sys
from pathlib import Path


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: render_template.py <template> <output>", file=sys.stderr)
        return 1

    template_path = Path(sys.argv[1])
    output_path = Path(sys.argv[2])
    content = template_path.read_text()

    for key, value in sorted(os.environ.items(), key=lambda item: len(item[0]), reverse=True):
        content = content.replace(f"${{{key}}}", value)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(content)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
