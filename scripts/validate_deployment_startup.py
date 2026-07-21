import argparse
import sys

from app.deployment import DeploymentProcess, validate_deployment_startup


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate provider-neutral deployment startup configuration."
    )
    parser.add_argument(
        "--process", choices=[process.value for process in DeploymentProcess], required=True
    )
    args = parser.parse_args()

    result = validate_deployment_startup(DeploymentProcess(args.process))
    for check in result.checks:
        status = "ok" if check.ok else "failed"
        print(f"{check.name}: {status} - {check.detail}")
    return 0 if result.ok else 1


if __name__ == "__main__":
    sys.exit(main())
