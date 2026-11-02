"""`app/core/permissions.py` — m7-roles-contract.md §1 sof funksiyalari.
DB/HTTP yo'q, har bir funksiya alohida sinaladi."""
from __future__ import annotations

from app.core.permissions import (
    ALL,
    CALLS_READ_OWN,
    ME_ALL,
    action_for_route,
    check_access,
    has_permission,
    has_region_access,
    is_picker_path,
    normalize_permissions,
    permissions_for,
    region_for_path,
    validate_permission_keys,
)


# --------------------------------------------------------------- permissions_for/has_permission
def test_permissions_for_admin_is_all():
    assert permissions_for("admin") == [ALL]


def test_permissions_for_operator_has_calls_and_me():
    assert permissions_for("operator") == [CALLS_READ_OWN, ME_ALL]


def test_permissions_for_unknown_role_is_empty():
    assert permissions_for("ghost") == []


def test_has_permission_admin_covers_anything():
    assert has_permission([ALL], "routing:edit") is True


def test_has_permission_exact_match_only_without_all():
    assert has_permission(["routing:view"], "routing:edit") is False
    assert has_permission(["routing:view"], "routing:view") is True


# --------------------------------------------------------------- normalize_permissions
def test_normalize_permissions_dedupes():
    assert normalize_permissions(["routing:view", "routing:view"]) == ["routing:view"]


def test_normalize_permissions_edit_implies_view_drops_view():
    result = normalize_permissions(["routing:view", "routing:edit"])
    assert result == ["routing:edit"]


def test_normalize_permissions_edit_first_still_drops_later_view():
    result = normalize_permissions(["routing:edit", "routing:view"])
    assert result == ["routing:edit"]


def test_normalize_permissions_leaves_special_keys_untouched():
    result = normalize_permissions([ALL, ME_ALL, CALLS_READ_OWN])
    assert result == [ALL, ME_ALL, CALLS_READ_OWN]


def test_normalize_permissions_independent_regions_both_kept():
    result = normalize_permissions(["routing:edit", "apps:view"])
    assert result == ["routing:edit", "apps:view"]


# --------------------------------------------------------------- validate_permission_keys
def test_validate_permission_keys_all_known_returns_none():
    assert validate_permission_keys(["routing:edit", "apps:view", ALL]) is None


def test_validate_permission_keys_unknown_returns_the_bad_key():
    assert validate_permission_keys(["routing:edit", "foo:edit"]) == "foo:edit"


def test_validate_permission_keys_rejects_unknown_region_known_action():
    assert validate_permission_keys(["billing:view"]) == "billing:view"


# --------------------------------------------------------------- region_for_path
def test_region_for_path_exact_prefix_match():
    assert region_for_path("/ivrs") == "routing"


def test_region_for_path_subresource_match():
    assert region_for_path("/ivrs/{ivr_id}") == "routing"


def test_region_for_path_longest_prefix_wins_for_settings_provisioning():
    assert region_for_path("/settings/provisioning") == "extensions"


def test_region_for_path_settings_without_provisioning_is_unmapped():
    assert region_for_path("/settings/sip") is None


def test_region_for_path_unmapped_system_routes_return_none():
    for path in ("/users", "/roles", "/settings", "/security", "/backups",
                 "/migration", "/audit", "/system", "/feature-codes", "/integrations"):
        assert region_for_path(path) is None, path


def test_region_for_path_calls_maps_to_reports():
    assert region_for_path("/calls") == "reports"


def test_region_for_path_does_not_match_unrelated_prefix_substring():
    # `/ivrsomething` boshqa marshrut emas, `/ivrs`ga mos tushmasligi kerak.
    assert region_for_path("/ivrsomething") is None


# --------------------------------------------------------------- action_for_route
def test_action_for_route_get_is_view():
    assert action_for_route("GET", "/ivrs") == "view"


def test_action_for_route_head_is_view():
    assert action_for_route("HEAD", "/ivrs") == "view"


def test_action_for_route_post_is_edit():
    assert action_for_route("POST", "/ivrs") == "edit"


def test_action_for_route_patch_delete_are_edit():
    assert action_for_route("PATCH", "/ivrs/{ivr_id}") == "edit"
    assert action_for_route("DELETE", "/ivrs/{ivr_id}") == "edit"


def test_action_for_route_simulate_exception_is_view_despite_post():
    assert action_for_route("POST", "/outbound-routes/simulate") == "view"


def test_action_for_route_trunk_test_is_not_an_exception():
    assert action_for_route("POST", "/trunks/{trunk_id}/test") == "edit"


# --------------------------------------------------------------- has_region_access
def test_has_region_access_all_grants_everything():
    assert has_region_access([ALL], "routing", "edit") is True


def test_has_region_access_edit_grants_view_and_edit():
    assert has_region_access(["routing:edit"], "routing", "view") is True
    assert has_region_access(["routing:edit"], "routing", "edit") is True


def test_has_region_access_view_only_grants_view_not_edit():
    assert has_region_access(["routing:view"], "routing", "view") is True
    assert has_region_access(["routing:view"], "routing", "edit") is False


def test_has_region_access_no_permission_denies():
    assert has_region_access(["apps:edit"], "routing", "view") is False


# --------------------------------------------------------------- is_picker_path
def test_is_picker_path_true_for_known_pickers():
    for path in ("/targets", "/targets/{target_id}/usages", "/flow/{inbound_route_id}",
                 "/numbers/free", "/extensions", "/audio", "/moh-classes", "/time-groups"):
        assert is_picker_path(path), path


def test_is_picker_path_false_for_non_picker_subresource():
    # `/extensions/{ext_id}/follow-me` umumiy tanlagich EMAS — ro'yxatda yo'q.
    assert is_picker_path("/extensions/{ext_id}/follow-me") is False


def test_is_picker_path_false_for_secret_revealing_routes():
    assert is_picker_path("/extensions/{ext_id}/rotate-secret") is False
    assert is_picker_path("/extensions/{ext_id}/secret") is False


# --------------------------------------------------------------- check_access — qaror jadvali
def test_check_access_admin_allowed_anywhere():
    assert check_access([ALL], "GET", "/roles") is True
    assert check_access([ALL], "POST", "/users") is True
    assert check_access([ALL], "DELETE", "/ivrs/{ivr_id}") is True


def test_check_access_operator_denied_region_routes():
    assert check_access([CALLS_READ_OWN, ME_ALL], "GET", "/ivrs") is False
    assert check_access([CALLS_READ_OWN, ME_ALL], "POST", "/ivrs") is False


def test_check_access_custom_role_view_allows_get_denies_write():
    perms = ["routing:view"]
    assert check_access(perms, "GET", "/ivrs") is True
    assert check_access(perms, "POST", "/ivrs") is False


def test_check_access_custom_role_edit_allows_get_and_write():
    perms = ["routing:edit"]
    assert check_access(perms, "GET", "/ivrs") is True
    assert check_access(perms, "POST", "/ivrs") is True


def test_check_access_custom_role_denied_outside_its_region():
    perms = ["routing:edit"]
    assert check_access(perms, "GET", "/trunks") is False


def test_check_access_system_routes_always_denied_without_all():
    perms = ["routing:edit", "apps:edit", "extensions:edit", "connect:edit", "reports:edit", "monitor:edit"]
    for path in ("/users", "/roles", "/settings", "/security", "/backups",
                 "/migration", "/audit", "/system", "/feature-codes", "/integrations"):
        assert check_access(perms, "GET", path) is False, path
        assert check_access(perms, "POST", path) is False, path


def test_check_access_picker_get_allowed_with_any_region_edit():
    assert check_access(["routing:edit"], "GET", "/extensions") is True


def test_check_access_picker_get_denied_with_view_only_role():
    assert check_access(["routing:view"], "GET", "/extensions") is False


def test_check_access_picker_get_denied_without_any_edit():
    assert check_access([CALLS_READ_OWN, ME_ALL], "GET", "/extensions") is False


def test_check_access_picker_post_not_exempted():
    # Tanlagich istisnosi FAQAT GET/HEAD uchun — POST hali ham o'z hududi talab qiladi.
    assert check_access(["routing:edit"], "POST", "/extensions") is False


def test_check_access_calls_reports_view_allows_full_access():
    assert check_access(["reports:view"], "GET", "/calls") is True
