"""Offline CLI; positional project identifier, never silent skip success."""
import argparse
import json
from pathlib import Path
import sys

from .core import Store, capability


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-root", type=Path, default=Path.home() / "Documents" / "CharacterSheets")
    parser.add_argument("operation", choices=("diagnose", "example", "compose", "verify", "export-upstream"))
    parser.add_argument("project", nargs="?")
    args = parser.parse_args()
    store = Store(args.data_root)
    try:
        if args.operation == "diagnose":
            result = capability()
        elif args.operation == "example":
            from .example import create_example
            m = create_example(store)
            result = store.compose(m["id"])
        else:
            if not args.project:
                raise ValueError("必须指定工程ID，缺失工程不计为核验成功")
            result = {"compose": store.compose, "verify": store.verify, "export-upstream": store.export_upstream}[args.operation](args.project)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0
    except Exception as e:
        print(json.dumps({"status": "fail", "error": str(e)}, ensure_ascii=False), file=sys.stderr)
        return 1


if __name__ == "__main__":
    sys.exit(main())
