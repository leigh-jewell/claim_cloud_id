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
from claim_cloud_id.constants import SAFE_MAX_BATCH_SIZE
from claim_cloud_id.csv_loader import load_cloud_ids_from_csv
from claim_cloud_id.logger import (
    emit_error,
    emit_info,
    emit_warning,
    log_error,
    log_info,
    log_warning,
    setup_file_logger,
)
from claim_cloud_id.report_writer import write_inventory_check_report
from dotenv import load_dotenv
import meraki


load_dotenv()


def get_dashboard_client(api_key: str) -> meraki.DashboardAPI:
    return meraki.DashboardAPI(
        api_key=api_key,
        suppress_logging=True,
        output_log=False,
        print_console=False,
    )


def list_accessible_orgs(dashboard: meraki.DashboardAPI) -> tuple[bool, str, list[dict] | None]:
    try:
        response = dashboard.organizations.getOrganizations()
    except meraki.APIError as exc:
        return False, f"Meraki API error {exc.status}: {exc.message}", None
    except Exception as exc:
        return False, f"Unexpected error: {exc}", None

    if not isinstance(response, list):
        return False, f"Unexpected SDK response type: {type(response).__name__}", None

    return True, f"found {len(response)} organization(s)", response


def claim_cloud_ids(
    dashboard: meraki.DashboardAPI,
    org_id: str,
    cloud_ids: list[str],
) -> tuple[bool, str, dict | None]:
    return run_inventory_action(dashboard, org_id, cloud_ids, action="claim")


def release_cloud_ids(
    dashboard: meraki.DashboardAPI,
    org_id: str,
    cloud_ids: list[str],
) -> tuple[bool, str, dict | None]:
    return run_inventory_action(dashboard, org_id, cloud_ids, action="release")


def run_inventory_action(
    dashboard: meraki.DashboardAPI,
    org_id: str,
    cloud_ids: list[str],
    action: str,
) -> tuple[bool, str, dict | None]:
    log_info(f"API call start: action={action}, org_id={org_id}, serial_count={len(cloud_ids)}")
    try:
        if action == "claim":
            response = dashboard.organizations.claimIntoOrganizationInventory(
                org_id,
                serials=cloud_ids,
            )
        else:
            response = dashboard.organizations.releaseFromOrganizationInventory(
                org_id,
                serials=cloud_ids,
            )
    except meraki.APIError as exc:
        log_error(f"API call failed: action={action}, status={exc.status}, error={exc.message}")
        return False, f"Meraki API error {exc.status}: {exc.message}", None
    except Exception as exc:
        log_error(f"API call failed unexpectedly: action={action}, error={exc}")
        return False, f"Unexpected error: {exc}", None

    if not isinstance(response, dict):
        return False, f"Unexpected SDK response type: {type(response).__name__}", None

    claimed_serials = response.get("serials")
    if claimed_serials is None:
        log_error(f"API call returned unexpected payload without serials: action={action}, payload={response}")
        return False, f"SDK response missing 'serials': {response}", response

    if not isinstance(claimed_serials, list):
        log_error(f"API call returned non-list serials: action={action}, serials={claimed_serials}")
        return False, f"SDK response 'serials' is not a list: {claimed_serials}", response

    log_info(f"API call success: action={action}, processed_serials={len(claimed_serials)}")
    return True, f"{get_action_past_tense(action)} {len(claimed_serials)} serial(s)", response


def get_inventory_devices(
    dashboard: meraki.DashboardAPI,
    org_id: str,
    cloud_ids: list[str],
) -> tuple[bool, str, list[dict] | None]:
    log_info(f"Inventory query start: org_id={org_id}, serial_count={len(cloud_ids)}")
    try:
        response = dashboard.organizations.getOrganizationInventoryDevices(
            org_id,
            serials=cloud_ids,
            perPage=1000,
            total_pages="all",
        )
    except meraki.APIError as exc:
        log_error(f"Inventory query failed: status={exc.status}, error={exc.message}")
        return False, f"Meraki API error {exc.status}: {exc.message}", None
    except Exception as exc:
        log_error(f"Inventory query failed unexpectedly: error={exc}")
        return False, f"Unexpected error: {exc}", None

    if not isinstance(response, list):
        log_error(f"Inventory query returned unexpected type: {type(response).__name__}")
        return False, f"Unexpected inventory response type: {type(response).__name__}", None

    log_info(f"Inventory query success: returned_devices={len(response)}")
    return True, f"fetched {len(response)} inventory device(s)", response


def get_inventory_devices_for_cloud_ids(
    dashboard: meraki.DashboardAPI,
    org_id: str,
    cloud_ids: list[str],
    batch_size: int,
) -> tuple[bool, str, list[dict] | None]:
    log_info(
        f"Inventory batch query start: org_id={org_id}, serial_count={len(cloud_ids)}, requested_batch_size={batch_size}"
    )
    effective_batch_size = batch_size
    current_index = 0
    used_backoff = False
    all_devices: list[dict] = []

    while current_index < len(cloud_ids):
        serial_batch = cloud_ids[current_index:current_index + effective_batch_size]
        success, message, inventory_devices = get_inventory_devices(dashboard, org_id, serial_batch)
        if not success:
            if effective_batch_size > SAFE_MAX_BATCH_SIZE and not used_backoff:
                emit_info(
                    f"Info: inventory query failed at size {effective_batch_size}; "
                    f"retrying with safe batch size {SAFE_MAX_BATCH_SIZE}."
                )
                effective_batch_size = SAFE_MAX_BATCH_SIZE
                used_backoff = True
                continue
            log_error(f"Inventory batch query failed with effective_batch_size={effective_batch_size}: {message}")
            return False, message, None

        all_devices.extend([device for device in (inventory_devices or []) if isinstance(device, dict)])
        current_index += len(serial_batch)

    log_info(
        f"Inventory batch query success: returned_devices={len(all_devices)}, effective_batch_size={effective_batch_size}"
    )
    return True, f"fetched {len(all_devices)} inventory device(s) in batches of {effective_batch_size}", all_devices


def get_network_bound_cloud_ids(
    dashboard: meraki.DashboardAPI,
    org_id: str,
    cloud_ids: list[str],
    batch_size: int,
) -> tuple[bool, str, list[str] | None]:
    success, message, inventory_devices = get_inventory_devices_for_cloud_ids(
        dashboard,
        org_id,
        cloud_ids,
        batch_size,
    )
    if not success:
        return False, message, None

    cloud_id_set = set(cloud_ids)
    bound_cloud_ids = sorted(
        {
            device.get("serial")
            for device in inventory_devices or []
            if device.get("serial") in cloud_id_set and device.get("networkId")
        }
    )

    return True, "checked network bindings for release", bound_cloud_ids


def run_inventory_action_in_batches(
    dashboard: meraki.DashboardAPI,
    org_id: str,
    cloud_ids: list[str],
    action: str,
    requested_batch_size: int,
) -> tuple[bool, str, list[str] | None, int]:
    log_info(
        f"Batched action start: action={action}, org_id={org_id}, serial_count={len(cloud_ids)}, requested_batch_size={requested_batch_size}"
    )
    effective_batch_size = requested_batch_size
    response_serials: list[str] = []
    current_index = 0
    used_backoff = False

    while current_index < len(cloud_ids):
        batch_serials = cloud_ids[current_index:current_index + effective_batch_size]
        success, message, response = run_inventory_action(
            dashboard,
            org_id,
            batch_serials,
            action,
        )
        if not success:
            if effective_batch_size > SAFE_MAX_BATCH_SIZE and not used_backoff:
                emit_info(
                    f"Info: batch request failed at size {effective_batch_size}; "
                    f"retrying with safe batch size {SAFE_MAX_BATCH_SIZE}."
                )
                effective_batch_size = SAFE_MAX_BATCH_SIZE
                used_backoff = True
                continue
            log_error(
                f"Batched action failed: action={action}, effective_batch_size={effective_batch_size}, error={message}"
            )
            return False, message, None, effective_batch_size

        batch_response_serials = response.get("serials", []) if response else []
        if not isinstance(batch_response_serials, list):
            log_error(
                f"Batched action returned non-list serials: action={action}, serials={batch_response_serials}"
            )
            return False, f"SDK response 'serials' is not a list: {batch_response_serials}", None, effective_batch_size

        response_serials.extend(batch_response_serials)
        current_index += len(batch_serials)

    verb = get_action_past_tense(action)
    log_info(
        f"Batched action success: action={action}, processed_serials={len(response_serials)}, effective_batch_size={effective_batch_size}"
    )
    return True, f"{verb} {len(response_serials)} serial(s) in batches of up to {effective_batch_size}", response_serials, effective_batch_size


def get_inventory_serials_for_cloud_ids(
    dashboard: meraki.DashboardAPI,
    org_id: str,
    cloud_ids: list[str],
    batch_size: int,
) -> tuple[bool, str, set[str] | None]:
    success, message, inventory_devices = get_inventory_devices_for_cloud_ids(
        dashboard,
        org_id,
        cloud_ids,
        batch_size,
    )
    if not success:
        return False, message, None

    found_serials: set[str] = set()
    batch_serials = {
        device.get("serial")
        for device in inventory_devices or []
        if isinstance(device, dict) and device.get("serial")
    }
    found_serials.update(batch_serials)

    return True, message, found_serials


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
