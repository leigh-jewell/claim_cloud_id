from claim_cloud_id.api_operations import (
    get_inventory_devices_for_cloud_ids,
    get_inventory_serials_for_cloud_ids,
    get_network_bound_cloud_ids,
    run_inventory_action_in_batches,
)
from claim_cloud_id.config import get_action_past_tense
from claim_cloud_id.logger import emit_error, emit_info, emit_warning
from claim_cloud_id.report_writer import write_inventory_check_report
import meraki


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


def handle_check_action(
    dashboard: meraki.DashboardAPI,
    org_id: str,
    cloud_ids: list[str],
    requested_batch_size: int,
    report_csv_path: str | None,
) -> tuple[bool, str]:
    if not report_csv_path:
        return False, "report CSV path is required for check action"

    success, message = check_cloud_ids_in_inventory(
        dashboard,
        org_id,
        cloud_ids,
        requested_batch_size,
        report_csv_path,
    )
    if not success:
        return False, message

    emit_info(f"[OK] {message}")
    return True, message


def prepare_claim_action_cloud_ids(
    dashboard: meraki.DashboardAPI,
    org_id: str,
    cloud_ids: list[str],
    requested_batch_size: int,
) -> tuple[bool, str, list[str] | None]:
    success, message, inventory_serials = get_inventory_serials_for_cloud_ids(
        dashboard,
        org_id,
        cloud_ids,
        requested_batch_size,
    )
    if not success:
        return False, f"failed pre-claim inventory check: {message}", None

    already_in_inventory = sorted(set(cloud_ids) & set(inventory_serials or set()))
    if already_in_inventory:
        emit_info("Info: the following cloud IDs are already in inventory and will be skipped:")
        for cloud_id in already_in_inventory:
            emit_info(f"- {cloud_id}")

    action_cloud_ids = [cloud_id for cloud_id in cloud_ids if cloud_id not in (inventory_serials or set())]
    if not action_cloud_ids:
        emit_info("Info: no claimable cloud IDs were found outside inventory.")
        return True, "no claimable cloud IDs", []

    return True, "prepared claim cloud IDs", action_cloud_ids


def prepare_release_action_cloud_ids(
    dashboard: meraki.DashboardAPI,
    org_id: str,
    cloud_ids: list[str],
    requested_batch_size: int,
) -> tuple[bool, str, list[str] | None]:
    success, message, inventory_serials = get_inventory_serials_for_cloud_ids(
        dashboard,
        org_id,
        cloud_ids,
        requested_batch_size,
    )
    if not success:
        return False, f"failed pre-release inventory check: {message}", None

    missing_from_inventory = sorted(set(cloud_ids) - set(inventory_serials or set()))
    if missing_from_inventory:
        emit_info("Info: the following cloud IDs were not found in inventory and will be skipped:")
        for cloud_id in missing_from_inventory:
            emit_info(f"- {cloud_id}")

    action_cloud_ids = [cloud_id for cloud_id in cloud_ids if cloud_id in (inventory_serials or set())]
    if not action_cloud_ids:
        emit_info("Info: no releasable cloud IDs were found in inventory.")
        return True, "no releasable cloud IDs", []

    success, message, bound_cloud_ids = get_network_bound_cloud_ids(
        dashboard,
        org_id,
        action_cloud_ids,
        requested_batch_size,
    )
    if not success:
        return False, f"failed pre-release network check: {message}", None

    if bound_cloud_ids:
        emit_warning("Release blocked. The following cloud IDs are bound to a network:")
        for cloud_id in bound_cloud_ids:
            emit_warning(f"- {cloud_id}")
        return False, "release blocked due to network-bound devices", None

    return True, "prepared release cloud IDs", action_cloud_ids


def execute_and_verify_action(
    dashboard: meraki.DashboardAPI,
    org_id: str,
    action: str,
    action_cloud_ids: list[str],
    requested_batch_size: int,
) -> tuple[bool, str]:
    success, message, response_serials, effective_batch_size = run_inventory_action_in_batches(
        dashboard,
        org_id,
        action_cloud_ids,
        action,
        requested_batch_size,
    )
    if not success:
        return False, message

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
        return False, "serial mismatch in API response"

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
        return False, verification_message

    emit_info(f"[OK] {verification_message}")
    return True, verification_message


def run_inventory_workflow(
    dashboard: meraki.DashboardAPI,
    org_id: str,
    action: str,
    cloud_ids: list[str],
    requested_batch_size: int,
    report_csv_path: str | None = None,
) -> tuple[bool, str]:
    if action == "check":
        return handle_check_action(
            dashboard,
            org_id,
            cloud_ids,
            requested_batch_size,
            report_csv_path,
        )

    if action == "claim":
        success, message, action_cloud_ids = prepare_claim_action_cloud_ids(
            dashboard,
            org_id,
            cloud_ids,
            requested_batch_size,
        )
        if not success:
            return False, message
        if not action_cloud_ids:
            return True, message
        return execute_and_verify_action(
            dashboard,
            org_id,
            action,
            action_cloud_ids,
            requested_batch_size,
        )

    if action == "release":
        success, message, action_cloud_ids = prepare_release_action_cloud_ids(
            dashboard,
            org_id,
            cloud_ids,
            requested_batch_size,
        )
        if not success:
            return False, message
        if not action_cloud_ids:
            return True, message
        return execute_and_verify_action(
            dashboard,
            org_id,
            action,
            action_cloud_ids,
            requested_batch_size,
        )

    return False, f"unsupported action: {action}"
