from claim_cloud_id.api_operations import (
    get_dashboard_client,
    get_inventory_devices_for_cloud_ids,
    get_inventory_serials_for_cloud_ids,
    get_network_bound_cloud_ids,
    list_accessible_orgs,
    run_inventory_action_in_batches,
)
from claim_cloud_id.cli import (
    get_action,
    get_batch_size,
    get_report_csv_path,
    parse_args,
    prompt_for_csv_path,
)
from claim_cloud_id.config import (
    get_action_past_tense,
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
from claim_cloud_id.report_writer import write_inventory_check_report
from dotenv import load_dotenv
import meraki


load_dotenv()


def check_cloud_ids_in_inventory(
    dashboard: meraki.DashboardAPI,
    org_id: str,
    cloud_ids: list[str],
    batch_size: int,
    report_csv_path: str,
) -> tuple[bool, str]:
    success, message, inventory_devices = get_inventory_devices_for_cloud_ids(
        dashboard,
        org_id,
        cloud_ids,
        batch_size,
    )
    if not success:
        return False, f"inventory check failed: {message}"

    inventory_serials = {
        device.get("serial")
        for device in inventory_devices or []
        if isinstance(device, dict) and device.get("serial")
    }
    network_ids_by_serial = {
        device.get("serial"): str(device.get("networkId"))
        for device in inventory_devices or []
        if isinstance(device, dict) and device.get("serial") and device.get("networkId")
    }

    in_inventory_count = len([cloud_id for cloud_id in cloud_ids if cloud_id in inventory_serials])
    missing_count = len(cloud_ids) - in_inventory_count

    emit_info("Inventory check summary:")
    emit_info(f"- Devices in CSV: {len(cloud_ids)}")
    emit_info(f"- In inventory: {in_inventory_count}")
    emit_info(f"- Missing from inventory: {missing_count}")

    report_success, report_message = write_inventory_check_report(
        report_csv_path,
        cloud_ids,
        inventory_serials,
        network_ids_by_serial,
    )
    if not report_success:
        return False, report_message

    emit_info(f"[OK] {report_message}")
    return True, "inventory check completed"


def verify_inventory_update(
    dashboard: meraki.DashboardAPI,
    org_id: str,
    cloud_ids: list[str],
    action: str,
    batch_size: int,
) -> tuple[bool, str, list[str] | None]:
    success, message, inventory_serials = get_inventory_serials_for_cloud_ids(
        dashboard,
        org_id,
        cloud_ids,
        batch_size,
    )
    if not success:
        return False, f"inventory verification failed: {message}", None

    if action == "claim":
        unmatched_serials = sorted(set(cloud_ids) - inventory_serials)
        if unmatched_serials:
            return False, "inventory verification failed after claim", unmatched_serials
        return True, "inventory verification passed after claim", []

    unmatched_serials = sorted(set(cloud_ids) & inventory_serials)
    if unmatched_serials:
        return False, "inventory verification failed after release", unmatched_serials
    return True, "inventory verification passed after release", []


def main():
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
        emit_info("No organisation ID provided and unable to determine a default. Please specify an organization ID with --org-id or set MERAKI_ORG_ID.")
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

    if action == "check":
        report_csv_path = get_report_csv_path(args.report_csv)
        success, message = check_cloud_ids_in_inventory(
            dashboard,
            org_id,
            cloud_ids,
            requested_batch_size,
            report_csv_path,
        )
        if not success:
            emit_error(f"[ERROR] {message}")
            raise SystemExit(1)
        emit_info(f"[OK] {message}")
        return

    action_cloud_ids = cloud_ids

    if action == "claim":
        success, message, inventory_serials = get_inventory_serials_for_cloud_ids(
            dashboard,
            org_id,
            cloud_ids,
            requested_batch_size,
        )
        if not success:
            emit_error(f"[ERROR] failed pre-claim inventory check: {message}")
            raise SystemExit(1)

        already_in_inventory = sorted(set(cloud_ids) & set(inventory_serials or set()))
        if already_in_inventory:
            emit_info("Info: the following cloud IDs are already in inventory and will be skipped:")
            for cloud_id in already_in_inventory:
                emit_info(f"- {cloud_id}")

        action_cloud_ids = [cloud_id for cloud_id in cloud_ids if cloud_id not in (inventory_serials or set())]
        if not action_cloud_ids:
            emit_info("Info: no claimable cloud IDs were found outside inventory.")
            return

    if action == "release":
        success, message, inventory_serials = get_inventory_serials_for_cloud_ids(
            dashboard,
            org_id,
            cloud_ids,
            requested_batch_size,
        )
        if not success:
            emit_error(f"[ERROR] failed pre-release inventory check: {message}")
            raise SystemExit(1)

        missing_from_inventory = sorted(set(cloud_ids) - set(inventory_serials or set()))
        if missing_from_inventory:
            emit_info("Info: the following cloud IDs were not found in inventory and will be skipped:")
            for cloud_id in missing_from_inventory:
                emit_info(f"- {cloud_id}")

        action_cloud_ids = [cloud_id for cloud_id in cloud_ids if cloud_id in (inventory_serials or set())]
        if not action_cloud_ids:
            emit_info("Info: no releasable cloud IDs were found in inventory.")
            return

        success, message, bound_cloud_ids = get_network_bound_cloud_ids(
            dashboard,
            org_id,
            action_cloud_ids,
            requested_batch_size,
        )
        if not success:
            emit_error(f"[ERROR] failed pre-release network check: {message}")
            raise SystemExit(1)

        if bound_cloud_ids:
            emit_warning("Release blocked. The following cloud IDs are bound to a network:")
            for cloud_id in bound_cloud_ids:
                emit_warning(f"- {cloud_id}")
            raise SystemExit(1)

    success, message, response_serials, effective_batch_size = run_inventory_action_in_batches(
        dashboard,
        org_id,
        action_cloud_ids,
        action,
        requested_batch_size,
    )

    if not success:
        emit_error(f"[ERROR] {message}")
        raise SystemExit(1)

    missing_serials = sorted(set(action_cloud_ids) - set(response_serials or []))
    action_past_tense = get_action_past_tense(action)

    emit_info(f"[OK] {message}")
    if response_serials:
        emit_info(f"{action_past_tense.capitalize()} serials:")
        for serial in response_serials:
            emit_info(f"- {serial}")

    if missing_serials:
        emit_error(f"Serials not reported as {action_past_tense} by the API response:")
        for serial in missing_serials:
            emit_error(f"- {serial}")
        raise SystemExit(1)

    verification_success, verification_message, unmatched_serials = verify_inventory_update(
        dashboard,
        org_id,
        action_cloud_ids,
        action,
        effective_batch_size,
    )
    if not verification_success:
        emit_error(f"[ERROR] {verification_message}")
        if unmatched_serials:
            if action == "claim":
                emit_error("Serials not found in inventory after claim:")
            else:
                emit_error("Serials still present in inventory after release:")
            for serial in unmatched_serials:
                emit_error(f"- {serial}")
        raise SystemExit(1)

    emit_info(f"[OK] {verification_message}")
    log_info("Run completed successfully")


if __name__ == "__main__":
    try:
        main()
    except (EnvironmentError, FileNotFoundError, ValueError) as exc:
        emit_error(f"Error: {exc}")
        raise SystemExit(1) from exc
    except KeyboardInterrupt:
        emit_warning("Interrupted by user")
        raise SystemExit(130)

