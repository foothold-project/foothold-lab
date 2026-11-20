"""Compare the two pinned APKs without decoding protected payloads."""
import argparse
import collections
import hashlib
import io
import json
from pathlib import Path
import tarfile
import xml.etree.ElementTree as ET
import zipfile

OLD_SHA = "71c9a34b1ec972f944007d4d8474e1bc3391dca1192fa2b46bc7b19be02a9e27"
NEW_SHA = "7a36e9a847997ebea02d88fde6ccdd6e5c4c8d3f7e57619584b3c6718bfa2cf1"


def compare(a, b):
    return {"added": sorted(b.keys()-a.keys()), "removed": sorted(a.keys()-b.keys()),
            "changed": sorted(k for k in a.keys() & b.keys() if a[k] != b[k]),
            "same": sorted(k for k in a.keys() & b.keys() if a[k] == b[k])}


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def inventory(archive):
    return {info.filename: {"bytes": info.file_size, "sha256": hashlib.sha256(archive.read(info)).hexdigest()}
            for info in archive.infolist() if not info.is_dir()}


def result(path, mcp=False):
    doc = read(path)
    if mcp:
        response = doc["response"]
        assert not response.get("error") and not response["result"].get("isError")
        return response["result"]["structuredContent"]["normalized_result"]
    assert "error" not in doc, path
    return doc["result"]


def main(a):
    # Known input exercises every distinction, including content rename vs path identity.
    known = compare({"same":1, "edited":1, "gone":1}, {"same":1, "edited":2, "new":1})
    assert known == {"added":["new"],"removed":["gone"],"changed":["edited"],"same":["same"]}
    assert hashlib.sha256(a.old.read_bytes()).hexdigest() == OLD_SHA
    assert hashlib.sha256(a.new.read_bytes()).hexdigest() == NEW_SHA
    old_ev, new_ev = a.data/"evidence", a.data/"latest-2.0.0/evidence"
    cp_old, cp_new = result(old_ev/"craft-package.json"), result(new_ev/"craft-package.json")
    rp_new = result(new_ev/"rea-package.json", True)
    for ck, rk in [("package","package_name"),("version_name","version_name"),
                   ("version_code","version_code"),("min_sdk","min_sdk"),("target_sdk","target_sdk")]:
        assert str(cp_new[ck]) == str(rp_new[rk])
    with zipfile.ZipFile(a.old) as zo, zipfile.ZipFile(a.new) as zn:
        assert zo.testzip() is None and zn.testzip() is None
        old, new = inventory(zo), inventory(zn)
        diff = compare(old, new)
        archive_bytes = zn.read("assets/dist/models/as2_description.tar.xz")
        with tarfile.open(fileobj=io.BytesIO(archive_bytes), mode="r:xz") as tar:
            members = [{"path":m.name,"bytes":m.size} for m in tar.getmembers()]
            urdf = ET.fromstring(tar.extractfile("as2_description/as2.urdf").read())
        urdf_info = {"name":urdf.get("name"),"links":len(urdf.findall("link")),
                     "joints":len(urdf.findall("joint")),
                     "joint_types":dict(collections.Counter(j.get("type") for j in urdf.findall("joint")))}
        new_js = []
        for name in new:
            if not name.endswith(".js"):
                continue
            try:
                zn.read(name).decode("utf-8")
                valid = True
            except UnicodeDecodeError:
                valid = False
            new_js.append({"path":name,"strict_utf8":valid})
        web_versions = [z.read("assets/dist/time.json").decode().splitlines() for z in [zo,zn]]
    old_components = {c["name"]:c for c in cp_old["manifest"]["components"]}
    new_components = {c["name"]:c for c in cp_new["manifest"]["components"]}
    component_diff = compare(old_components, new_components)
    locale_diffs = {}
    resources = []
    for ev in [old_ev,new_ev]:
        r = result(ev/"rea-resources.json",True)
        resources.append({t.get("locale") or "default":{s["name"]:s["value"] for s in t.get("strings",[])}
                          for t in r["string_tables"]})
    for loc in sorted(resources[0].keys() | resources[1].keys()):
        x,y=resources[0].get(loc,{}),resources[1].get(loc,{})
        locale_diffs[loc]={"old_count":len(x),"new_count":len(y),**compare(x,y)}
        locale_diffs[loc]["same_count"] = len(locale_diffs[loc].pop("same"))
    # Only UI names identified in the comparison are copied, not arbitrary configuration.
    selected = [k for k in locale_diffs["default"]["added"]+locale_diffs["default"]["changed"]
                if not any(s in k.lower() for s in ["pwd","password","key","token","secret"])]
    ui = [{"key":k,"old":resources[0]["default"].get(k),"new":resources[1]["default"][k]}
          for k in selected]
    permissions_old, permissions_new = map(set,[cp_old["manifest"]["uses_permissions"],cp_new["manifest"]["uses_permissions"]])
    summary = {
        "schema":"foothold-apk-version-diff/1", "old_sha256":OLD_SHA, "new_sha256":NEW_SHA,
        "known_input":"PASS", "manifest_identity_two_parsers":"PASS", "zip_crc":"PASS",
        "web_versions":web_versions,
        "versions":[{k:cp[k] for k in ["package","version_name","version_code","min_sdk","target_sdk","entries","assets"]} for cp in [cp_old,cp_new]],
        "zip_diff_counts":{k:len(v) for k,v in diff.items()},
        "added_asset_paths":[p for p in diff["added"] if p.startswith("assets/")],
        "changed_native_paths":[p for p in diff["changed"] if p.startswith("lib/")],
        "unchanged_models_and_wasm":[p for p in diff["same"] if p.endswith((".glb",".wasm"))],
        "component_diff":component_diff,
        "component_counts":[dict(collections.Counter(x["kind"] for x in cp["manifest"]["components"])) for cp in [cp_old,cp_new]],
        "permissions":{"added":sorted(permissions_new-permissions_old),"removed":sorted(permissions_old-permissions_new)},
        "resource_diffs":locale_diffs,"selected_ui_changes":ui,
        "new_robot_archive":{"path":"assets/dist/models/as2_description.tar.xz","sha256":hashlib.sha256(archive_bytes).hexdigest(),"members":members,"urdf":urdf_info},
        "new_javascript":new_js,
        "old_analysis_byte_identity":"Same SHA as REPORT-astra-10.md from 2026-10-13",
        "limitations":["File name changes are not feature changes","Resource presence is not activation",
                       "No protected payload decoding or app/robot runtime","No paid tool execution"]
    }
    a.output.mkdir(parents=True,exist_ok=True)
    (a.output/"version-diff.json").write_text(json.dumps(summary,ensure_ascii=False,indent=2)+'\n')
    print(json.dumps({"output":str(a.output),"counts":summary["zip_diff_counts"],
                     "UI_added":len(locale_diffs['default']['added']),"UI_changed":len(locale_diffs['default']['changed']),
                     "components_added":len(component_diff['added']),"components_removed":len(component_diff['removed'])}))


if __name__ == "__main__":
    parser=argparse.ArgumentParser()
    for name in ['old','new','data','output']:
        parser.add_argument('--'+name,type=Path,required=True)
    main(parser.parse_args())
