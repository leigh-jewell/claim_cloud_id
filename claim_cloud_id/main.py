from claim_cloud_id.api_operations import (
    get_dashboard_client,
    list_accessible_orgs,
)
from claim_cloud_id.cli import (
    get_action,
    get_batch_size,
    get_report_csv_path,
    parse_args,
    prompt_for_csv_path,
)
from claim_cloud_id.config import (
    get_dashboard_api_key,
    get_log_file_path,
    get_org_id,
)
from claim_cloud_id.csv_loader import load_cloud_ids_from_csv
from claim_cloud_id.logger import (
    emit_error,
    emit_info,
    emit_warning,
    log_info,
    setup_file_logger,
)
from claim_cloud_id.orchestrator import run_inventory_workflow
from dotenv import load_dotenv


load_dotenv()


def main() -> None:
    try:
        args = parse_args()
        log_file_path = get_log_file_path(args.log_file)
        resolved_log_path = setup_file_logger(log_file_path)
        emit_info(f"Logging to {resolved_log_path}")
        log_info("Run started")

        api_key = get_dashboard_api_key()
        dashboard = get_dashboard_client(api_key)
        org_id = get_org_id(args.org_id)

        if not org_id:
            success, message, organizations = list_accessible_orgs(dashboard)
            if not success:
                emit_error(f"[ERROR] {message}")
                raise SystemExit(1)

            emit_info(f"No MERAKI_ORG_ID provided. {message} available to this API key:")
            for organization in organizations or []:
                name = organization.get("name", "<unknown>")
                organization_id = organization.get("id", "<missing id>")
                emit_info(f"- {name}: {organization_id}")
            raise SystemExit(0)

        action = get_action(args.action)
        requested_batch_size = get_batch_size(args.batch_size)
        csv_path = args.csv_path or prompt_for_csv_path()
        cloud_ids = load_cloud_ids_from_csv(csv_path)
        emit_info(
            f"Loaded {len(cloud_ids)} cloud IDs from {csv_path} for {action} "
            f"with requested batch size {requested_batch_size}"
        )

        report_csv_path = get_report_csv_path(args.report_csv) if action == "check" else None
        if args.dry_run:
            emit_info("[DRY RUN] Previewing action — no inventory changes will be made.")
        success, message = run_inventory_workflow(
            dashboard,
            org_id,
            action,
            cloud_ids,
            requested_batch_size,
            report_csv_path,
            dry_run=args.dry_run,
        )
        if not success:
            emit_error(f"[ERROR] {message}")
            raise SystemExit(1)

        log_info("Run completed successfully")

    except SystemExit:
        raise
    except (EnvironmentError, FileNotFoundError, ValueError) as exc:
        emit_error(f"Error: {exc}")
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        emit_warning("Interrupted by user")
        raise SystemExit(130)


if __name__ == "__main__":
    main()
