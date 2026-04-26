from claim_cloud_id.config import get_action_past_tense
from claim_cloud_id.constants import SAFE_MAX_BATCH_SIZE
from claim_cloud_id.logger import emit_info, log_error, log_info
import meraki


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
        log_error(
            f"API call returned unexpected payload without serials: action={action}, "
            f"payload_keys={list(response.keys())}"
        )
        return False, f"SDK response missing 'serials' key (got keys: {list(response.keys())})", response

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

    batch_serials = {
        device.get("serial")
        for device in inventory_devices or []
        if isinstance(device, dict) and device.get("serial")
    }

    return True, message, batch_serials
