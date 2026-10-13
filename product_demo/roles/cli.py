"""Run with python -m product_demo.roles.cli from the repository root."""

import argparse
import json
from pathlib import Path

from .policy import AccessDenied, Action, Role, RoleStore


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="S-02 synthetic local role demo; no SSO")
    parser.add_argument("--store", type=Path, required=True,
                        help="Operator-owned synthetic JSON file, preferably outside the repo")
    commands = parser.add_subparsers(dest="command", required=True)
    commands.add_parser("init", help="Create fixtures; refuses to overwrite")
    assign = commands.add_parser("assign")
    assign.add_argument("--actor", required=True)
    assign.add_argument("--subject", required=True)
    assign.add_argument("--role", choices=[role.value for role in Role], required=True)
    read = commands.add_parser("role")
    read.add_argument("--subject", required=True)
    probe = commands.add_parser("probe", help="Exercise a guard; not a booking or catalog change")
    probe.add_argument("--actor", required=True)
    probe.add_argument("--action", required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "init":
            RoleStore.initialize(args.store)
            result = {"synthetic": True, "initialized": True}
        else:
            store = RoleStore(args.store)
            if args.command == "assign":
                store.assign(args.actor, args.subject, args.role)
                result = {"subject": args.subject, "role": RoleStore(args.store).role_for(args.subject)}
            elif args.command == "role":
                # Fixture roles are not secrets; this is an operator diagnostic, not an API.
                result = {"subject": args.subject, "role": store.role_for(args.subject)}
            else:
                result = store.guarded(args.actor, args.action,
                                       lambda: {"allowed": True, "probe_executed": True,
                                                "business_operation_implemented": False})
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0
    except AccessDenied as error:
        print(json.dumps({"allowed": False, "probe_executed": False, "error": str(error)}))
        return 3
    except (OSError, ValueError) as error:
        print(json.dumps({"error": str(error)}, ensure_ascii=False))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
