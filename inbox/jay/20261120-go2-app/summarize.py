"""Recalculate safe, shareable APK facts from local original bytes and tool evidence.

No decryption, APK execution, robot connection, or credential values in output.
Full vendor resources and tool responses stay in the local data directory.
"""
import argparse
import collections
import csv
import hashlib
import html
import json
from pathlib import Path
import struct
import zipfile

APK_SHA = "71c9a34b1ec972f944007d4d8474e1bc3391dca1192fa2b46bc7b19be02a9e27"
WASM = {
    "libvoxel-Bqa6xB-f.wasm": "df28d833bc3045e58e110926dd87c312538a2e5b60a964a4fc5e99ff06d39b9c",
    "libvoxel-doIu-r8s.wasm": "1ba27f065199954dc562b233aa38ea775ac687118cce77b5c71bc14e17e05542",
}
# Explicit resource-name allowlist. Never publish arbitrary resource values.
UI_KEYS = {
    "app_main_simulator", "app_simulator_title", "app_main_slam", "app_slam_title",
    "app_map_3d_title", "app_dog_stop", "app_robot_disconnect", "app_dog_disconnect_tip",
    "app_have_been_reconnected", "app_no_sport_tip", "app_sport_not_support",
    "app_sport_switch_success", "app_sport_close_failure", "stop_sport_mode",
    "app_mode_ai", "app_mode_ai_tip", "app_mode_leading", "app_mode_leading_tip",
    "app_mode_normal", "app_mode_normal_tip", "title_default_sport", "tip_default_sport",
    "app_save_point", "app_point_name_hint", "app_change_wifi_tip", "app_open_wifi_tip",
    "connect_wifi_failure", "wifi_success", "setting_wifi_info", "wifi_connecting",
    "app_data_title_radar", "app_lidar_title_radar", "app_data_title_battery",
    "app_battery_title_power", "app_battery_title_voltage", "app_battery_title_count",
    "app_battery_title_tem1", "app_battery_title_tem2", "app_battery_title_tem3",
    "app_data_motor0", "app_data_motor1", "app_data_motor2", "app_data_motor3",
    "app_load_mass", "app_load_center", "app_load_inertia", "app_load_tip_in",
    "app_title_config_load", "app_title_config_offset", "app_offset_tau", "app_offset_tip_in",
    "app_title_standard_ask", "app_title_standard", "app_title_leg_standard",
    "app_dog_follow", "app_follow_distance", "app_follow_orientation", "app_follow_mode",
    "app_follow_base", "app_follow_tag", "app_follow_yaw", "app_follow_pitching", "app_follow_roll",
    "voice_assistant", "voice_volume", "voice_word", "app_remote_switch",
    "remote_tip", "remote_setting_title", "remote_type_action", "remote_type_mode",
    "title_dog_upload", "app_com_rotation_speed", "app_sys_rotation_speed",
} | {f"app_joy_mode_{i}" for i in range(9)}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def rea(path):
    response = read_json(path)["response"]
    if response.get("error") or response.get("result", {}).get("isError"):
        raise ValueError(f"REA tool failed: {path}")
    e = response["result"]["structuredContent"]
    return e


def craft(path):
    e = read_json(path)
    if "error" in e:
        raise ValueError(f"Craft tool failed despite possible rc=0: {path}")
    return e


def tsv(path, fields, rows):
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=fields, delimiter="\t", extrasaction="ignore", lineterminator="\n")
        writer.writeheader()
        writer.writerows({key: "null" if row.get(key) is None else row[key] for key in fields} for row in rows)


def main(a):
    data = a.apk.read_bytes()
    assert digest(data) == APK_SHA, "This report is pinned to APK 1.12.10 bytes"
    ev = a.data / "evidence"
    cp = craft(ev / "craft-package.json")
    rp = rea(ev / "rea-package.json")
    rs = rea(ev / "rea-resources.json")
    for item in [rp, rs]:
        assert item["subject"]["identity"]["sha256"] == APK_SHA
    assert cp["subject"]["sha256"] == APK_SHA
    c, r = cp["result"], rp["normalized_result"]
    for ck, rk in [("package", "package_name"), ("version_name", "version_name"),
                   ("version_code", "version_code"), ("min_sdk", "min_sdk"), ("target_sdk", "target_sdk")]:
        assert str(c[ck]) == str(r[rk]), (ck, c[ck], r[rk])
    # Known inputs test semantics, not just tool exit status.
    known = craft(ev / "craft-known-zip.json")["result"]
    assert known["files"] == known["entries_total"] == 2
    for entry in known["entries"]:
        assert entry["sha256"] == digest({"a.txt": b"alpha\n", "dir/b.txt": b"beta\n"}[entry["path"]])
    graph = rea(ev / "rea-known-js.json")["normalized_result"]["graph"]
    for kind, label in [("ipc-channel", "fixture:echo"), ("context-bridge-api", "fixtureApi")]:
        assert any(n["kind"] == kind and any(o.get("label") == label for o in n["observations"])
                   for n in graph["nodes"]), (kind, label)

    inventory, glbs, dex, js = [], [], [], []
    with zipfile.ZipFile(a.apk) as archive:
        assert archive.testzip() is None, "ZIP CRC mismatch"
        for info in archive.infolist():
            if info.is_dir():
                continue
            buf = archive.read(info)
            row = {"path": info.filename, "bytes": len(buf), "sha256": digest(buf)}
            inventory.append(row)
            if info.filename.endswith(".wasm"):
                assert row["sha256"] == WASM[Path(info.filename).name]
            if info.filename.endswith(".dex") and buf[:4] == b"dex\n":
                dex.append({**row, "class_definitions": struct.unpack_from("<I", buf, 96)[0]})
            if info.filename.endswith(".js"):
                try:
                    buf.decode("utf-8")
                    valid = True
                except UnicodeDecodeError:
                    valid = False
                js.append({**row, "strict_utf8": valid})
            if info.filename.endswith(".glb"):
                magic, version, size = struct.unpack_from("<4sII", buf)
                assert (magic, version, size) == (b"glTF", 2, len(buf))
                length, chunk = struct.unpack_from("<I4s", buf, 12)
                assert chunk == b"JSON"
                doc = json.loads(buf[20:20 + length])
                anims = []
                for anim in doc.get("animations", []):
                    times = [doc["accessors"][s["input"]] for s in anim["samplers"]]
                    start = min(x["min"][0] for x in times)
                    end = max(x["max"][0] for x in times)
                    anims.append({"name": anim.get("name"), "start_s": start, "end_s": end,
                                  "duration_s": end-start, "channels": len(anim["channels"]),
                                  "paths": sorted({x["target"]["path"] for x in anim["channels"]})})
                glbs.append({**row, "nodes": len(doc.get("nodes", [])),
                             "skins": len(doc.get("skins", [])), "meshes": len(doc.get("meshes", [])),
                             "generator": doc["asset"].get("generator"), "animations": anims})
        web_version = archive.read("assets/dist/time.json").decode().splitlines()

    assert sum(x["class_definitions"] for x in dex) == sum(x["classes"] for x in c["dex"])
    wasm_tests = []
    for mode in ["points", "mesh"]:
        result = read_json(a.data / "wasm-fixtures" / f"fixtures-{mode}.json")
        assert result["assertions_passed"] and result["sha256"] in WASM.values()
        wasm_tests.append({"mode": mode, "tests": len(result["tests"]), "sha256": result["sha256"],
                           "memory_bytes": result["memory_bytes"], "assertions_passed": True})
    selected = []
    locale_counts = []
    for table in rs["normalized_result"]["string_tables"]:
        locale = table.get("locale") or "default"
        locale_counts.append({"locale": locale, "status": table["status"], "count": len(table.get("strings", []))})
        for string in table.get("strings", []):
            if string["name"] in UI_KEYS:
                selected.append({"locale": locale, "key": string["name"], "value": html.unescape(string["value"])})
    # R is generated/reported by JADX; do not confuse it with a raw DEX app definition.
    class_search = craft(ev / "craft-unitree-classes.json")["result"]
    rea_class_search = rea(ev / "rea-unitree-classes.json")["normalized_result"]
    m = c["manifest"]
    summary = {
        "schema": "foothold-apk-static-analysis/1", "apk": {"path": str(a.apk), "sha256": APK_SHA,
        "bytes": len(data), "package": c["package"], "version_name": c["version_name"],
        "version_code": c["version_code"], "min_sdk": c["min_sdk"], "target_sdk": c["target_sdk"],
        "zip_entries": c["entries"], "web_version_text": web_version},
        "known_input_checks": {"rea_ipc_bridge": True, "craft_zip_count_hash": True,
                               "cross_parser_manifest_identity": True, "apk_crc": True},
        "components": dict(collections.Counter(x["kind"] for x in m["components"])),
        "application": {k:m["application"].get(k) for k in ["name", "uses_cleartext_traffic", "network_security_config"]},
        "permissions": r["permissions"], "native_libraries": c["native_libraries"],
        "dex": dex, "java_class_counts": {"raw_definitions": sum(x["class_definitions"] for x in dex),
                                           "jadx_package_count": r["class_count"]},
        "unitree_class_search": {"raw_matches": class_search["matches"],
                                  "jadx_matches": rea_class_search["matches"],
                                  "scope": "Visible DEX only; protected payload not decoded"},
        "javascript": js, "models": glbs, "wasm_tests": wasm_tests, "locale_tables": locale_counts,
        "dependencies": read_json(ev / "dependency-classes.json"),
        "signature_craft": c["signing"],
        "signature_rea": rea(ev / "rea-signature.json")["normalized_result"],
        "tool_evidence": {"rea_package": rp["evidence_id"], "rea_resources": rs["evidence_id"],
                          "craft_package": cp["id"]},
        "limits": ["No protected payload decryption", "No app runtime or robot session",
                   "No 1.12.10 JS call-path verification", "No latency or actual Go2 X capability measurement",
                   "Resource names and manifest entries do not prove feature activation"],
    }
    a.output.mkdir(parents=True, exist_ok=True)
    (a.output / "evidence-summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n")
    tsv(a.output / "UI-EVIDENCE.tsv", ["locale", "key", "value"], selected)
    tsv(a.output / "COMPONENTS.tsv", ["kind", "name", "exported", "enabled"], m["components"])
    tsv(a.output / "ASSET-HASHES.tsv", ["path", "bytes", "sha256"],
        [x for x in inventory if x["path"].startswith("assets/dist/")])
    (ev / "apk-inventory-v2.json").write_text(json.dumps(inventory, indent=2) + "\n")
    print(json.dumps({"output": str(a.output), "wasm_tests": sum(x["tests"] for x in wasm_tests),
                      "ui_rows": len(selected), "known_inputs": "PASS", "models": len(glbs)}))


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--apk", type=Path, required=True)
    parser.add_argument("--data", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    main(parser.parse_args())
