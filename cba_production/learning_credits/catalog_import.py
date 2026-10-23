"""Map catalog/Studio exports to draft plans without trusting approval flags."""

from copy import deepcopy
from opaque_keys.edx.keys import CourseKey, UsageKey

from .calculations import ACTIVITY_CATEGORIES, CREDIT_POLICY_VERSION, calculate_credits


def catalog_plan_records(payload):
    if not isinstance(payload, dict):
        raise ValueError("The catalog must be an object.")
    if "course_key" in payload and "credit_plan" in payload:
        records = [payload]
    elif "credit_plans" in payload:
        records = payload["credit_plans"]
    else:
        records = payload.get("microcourses", [])
    if not isinstance(records, list) or not records:
        raise ValueError("Supply a course credit export, credit_plans array, or microcourses array.")
    sidecars = payload.get("sidecar", payload.get("sidecars", {}))
    if not isinstance(sidecars, dict):
        raise ValueError("Sidecars must be an object.")
    if "sidecar" in payload and "sidecars" in payload and payload["sidecar"] != payload["sidecars"]:
        raise ValueError("sidecar and sidecars must match.")
    result, seen = [], set()
    for record in records:
        if not isinstance(record, dict):
            raise ValueError("Each course must be an object.")
        key = record.get("course_key")
        if not isinstance(key, str) or str(CourseKey.from_string(key)) != key:
            raise ValueError("Use canonical course keys.")
        if key in seen:
            raise ValueError("Duplicate course key: " + key)
        seen.add(key)
        sidecar = sidecars.get(key, {})
        if not isinstance(sidecar, dict):
            raise ValueError("Each sidecar must be an object.")
        raw = record.get("credit_plan", sidecar.get("credit_plan", {}))
        if "credit_plan" in record and "credit_plan" in sidecar and record["credit_plan"] != sidecar["credit_plan"]:
            raise ValueError("Record and sidecar credit plans disagree: " + key)
        if not isinstance(raw, dict):
            raise ValueError("credit_plan must be an object.")
        allowed = {
            "version", "status", "activity_minutes", "instructional_design_reference",
            "learning_outcomes", "required_block_keys", "activity_requirements", "policy_version",
        }
        if set(raw) - allowed:
            raise ValueError("Unknown credit-plan fields: " + ", ".join(sorted(set(raw) - allowed)))
        version = raw.get("version", 1)
        if type(version) is not int or not 1 <= version <= 2147483647:
            raise ValueError("Credit plan version must be a positive integer.")
        if raw.get("policy_version", CREDIT_POLICY_VERSION) != CREDIT_POLICY_VERSION:
            raise ValueError("Unsupported credit policy version.")
        minutes = deepcopy(raw.get("activity_minutes", {name: None for name in ACTIVITY_CATEGORIES}))
        calculate_credits(minutes)
        values = {
            "course_key": key, "version": version,
            "instructional_design_reference": raw.get("instructional_design_reference", ""),
            "learning_outcomes": deepcopy(raw.get("learning_outcomes", record.get("learning_outcomes", []))),
            "required_block_keys": deepcopy(raw.get("required_block_keys", [])),
            "activity_requirements": deepcopy(raw.get("activity_requirements", [])),
        }
        if not isinstance(values["required_block_keys"], list):
            raise ValueError("required_block_keys must be an array.")
        for value in values["required_block_keys"]:
            block = UsageKey.from_string(value)
            if str(block) != value or str(block.course_key) != key:
                raise ValueError("Required activities must belong to their course run.")
        values.update({name + "_minutes": minutes[name] for name in ACTIVITY_CATEGORIES})
        result.append(values)
    return result
