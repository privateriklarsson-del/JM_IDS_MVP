import streamlit as st
import ifcopenshell
import ifcopenshell.util.element
import ifctester
import ifctester.ids
import tempfile
import os
import json
import numpy as np
from pathlib import Path
from datetime import datetime
from bcf.v2.bcfxml import BcfXml
from bcf.v2 import model as mdl

# --- Config ---
IDS_FOLDER = Path("ids_files")
APP_TITLE = "JM IDS Checker"
MAX_UPLOAD_MB = 300


def load_ids_files():
    ids_files = {}
    if IDS_FOLDER.exists():
        for f in sorted(IDS_FOLDER.glob("*.ids")):
            try:
                ids_obj = ifctester.ids.open(str(f))
                ids_files[f.stem] = {"path": f, "ids": ids_obj}
            except Exception as e:
                st.warning(f"Could not load {f.name}: {e}")
    return ids_files


def add_bcf_viewpoint(topic, issue, ifc_file):
    first_entity = issue.get("first_entity")
    guids = issue.get("guids", [])

    if first_entity is not None and hasattr(first_entity, 'ObjectPlacement') and first_entity.ObjectPlacement:
        viewpoint = topic.add_viewpoint(first_entity)
        if len(guids) > 1:
            vi = viewpoint.visualization_info
            if vi.components and vi.components.selection:
                existing = {c.ifc_guid for c in vi.components.selection.component}
                for guid in guids:
                    if guid not in existing:
                        vi.components.selection.component.append(mdl.Component(ifc_guid=guid))
    elif guids:
        fallback = None
        if ifc_file is not None:
            try:
                fallback = ifc_file.by_guid(guids[0])
            except Exception:
                pass
        if fallback is not None and hasattr(fallback, 'ObjectPlacement') and fallback.ObjectPlacement:
            viewpoint = topic.add_viewpoint(fallback)
            if len(guids) > 1:
                vi = viewpoint.visualization_info
                if vi.components and vi.components.selection:
                    existing = {c.ifc_guid for c in vi.components.selection.component}
                    for guid in guids:
                        if guid not in existing:
                            vi.components.selection.component.append(mdl.Component(ifc_guid=guid))
        else:
            topic.add_viewpoint_from_point_and_guids(np.array([0.0, 0.0, 5.0]), *guids)


def main():
    st.set_page_config(page_title=APP_TITLE, page_icon="\U0001F3D7\uFE0F", layout="wide")

    # --- Sidebar ---
    with st.sidebar:
        st.title(APP_TITLE)
        st.markdown("---")
        st.markdown(
            "1. Upload IFC file\n"
            "2. Select rule sets\n"
            "3. Click **Run**\n"
            "4. Download BCF"
        )
        st.markdown("---")
        st.markdown("*MVP v1.0*")

    # --- Main ---
    st.title(f"\U0001F3D7\uFE0F {APP_TITLE}")

    ids_files = load_ids_files()
    if not ids_files:
        st.error(f"No .ids files found in `{IDS_FOLDER}/`")
        return

    uploaded_file = st.file_uploader("Upload IFC file", type=["ifc"])

    st.subheader("Rule sets")
    selected_ids = []
    cols = st.columns(2)
    for i, (name, data) in enumerate(ids_files.items()):
        with cols[i % 2]:
            ids_obj = data["ids"]
            info = ""
            if hasattr(ids_obj, 'info') and ids_obj.info and hasattr(ids_obj.info, 'description'):
                info = ids_obj.info.description
            if st.checkbox(name.replace("_", " "), value=True, help=info):
                selected_ids.append((name, data))

    st.markdown("---")
    run = st.button("\U0001F680 Run Validation", type="primary", disabled=uploaded_file is None)

    if run and uploaded_file is not None:
        with tempfile.NamedTemporaryFile(suffix=".ifc", delete=False) as tmp:
            tmp.write(uploaded_file.getvalue())
            tmp_path = tmp.name

        try:
            with st.spinner("Parsing IFC..."):
                ifc_file = ifcopenshell.open(tmp_path)

            st.success(
                f"**{uploaded_file.name}** — "
                f"Schema: {ifc_file.schema}, "
                f"Elements: {len(list(ifc_file))}"
            )

            all_results = []
            bcf_issues = []

            for name, data in selected_ids:
                ids_obj = ifctester.ids.open(str(data["path"]))

                with st.spinner(f"Checking: {name.replace('_', ' ')}..."):
                    ids_obj.validate(ifc_file)

                st.subheader(f"\U0001F4CB {name.replace('_', ' ')}")

                for spec in ids_obj.specifications:
                    applicable = spec.applicable_entities if spec.applicable_entities else []
                    total = len(applicable)

                    if spec.status is True:
                        st.markdown(f"\u2705 **{spec.name}** — {total} checked, all passed")
                        all_results.append({"rule_set": name, "rule": spec.name, "status": "PASS", "elements_checked": total})

                    elif spec.status is False:
                        failures = {}
                        for req in spec.requirements:
                            if hasattr(req, 'failures') and req.failures:
                                for failure in req.failures:
                                    if isinstance(failure, dict):
                                        entity = failure.get("element") or failure.get("entity")
                                        reason = failure.get("reason", "Unknown")
                                    else:
                                        entity = getattr(failure, 'element', None) or getattr(failure, 'entity', None)
                                        reason = getattr(failure, 'reason', "Unknown")
                                    if entity is None:
                                        continue
                                    eid = entity.id()
                                    if eid not in failures:
                                        psets = ifcopenshell.util.element.get_psets(entity)
                                        type_id = psets.get("JM", {}).get("TypeID", "")
                                        failures[eid] = {
                                            "type": entity.is_a(),
                                            "name": entity.Name if hasattr(entity, 'Name') and entity.Name else "\u2014",
                                            "type_id": type_id,
                                            "reasons": [],
                                            "entity": entity,
                                        }
                                    failures[eid]["reasons"].append(str(reason))

                        fail_count = len(failures)
                        with st.expander(f"\u274C **{spec.name}** — {fail_count} failed", expanded=False):
                            rows = []
                            for eid, info in sorted(failures.items()):
                                rows.append({
                                    "ID": f"#{eid}",
                                    "Type": info["type"],
                                    "Name": info["name"],
                                    "TypeID": info["type_id"],
                                    "Reason": "; ".join(info["reasons"][:3]),
                                })
                            st.dataframe(rows, use_container_width=True, hide_index=True)
                            passed = total - fail_count
                            if passed > 0:
                                st.markdown(f"*{passed} elements passed.*")

                        # BCF
                        guids = []
                        first_entity = None
                        for eid, info in failures.items():
                            guid = getattr(info["entity"], 'GlobalId', None)
                            if guid:
                                guids.append(guid)
                                if first_entity is None:
                                    first_entity = info["entity"]
                        if guids:
                            bcf_issues.append({
                                "title": f"{name}: {spec.name}",
                                "description": f"{fail_count} elements failed. Rule set: {name}",
                                "guids": guids,
                                "first_entity": first_entity,
                            })

                        all_results.append({"rule_set": name, "rule": spec.name, "status": "FAIL", "elements_checked": total})
                    else:
                        st.markdown(f"\u26A0\uFE0F **{spec.name}** — No applicable elements")
                        all_results.append({"rule_set": name, "rule": spec.name, "status": "N/A", "elements_checked": 0})

            # --- Summary ---
            st.markdown("---")
            st.subheader("\U0001F4CA Summary")
            total_rules = len(all_results)
            passed = sum(1 for r in all_results if r["status"] == "PASS")
            failed = sum(1 for r in all_results if r["status"] == "FAIL")
            na = sum(1 for r in all_results if r["status"] == "N/A")

            c1, c2, c3 = st.columns(3)
            c1.metric("Passed", f"{passed}/{total_rules}")
            c2.metric("Failed", f"{failed}/{total_rules}")
            c3.metric("N/A", f"{na}/{total_rules}")

            # Store for export
            st.session_state.last_results = all_results
            st.session_state.last_bcf_issues = bcf_issues
            st.session_state.last_ifc_file = ifc_file
            st.session_state.last_filename = uploaded_file.name

        except Exception as e:
            st.error(f"Validation error: {e}")
            st.exception(e)
        finally:
            os.unlink(tmp_path)

    # --- Export ---
    if "last_results" in st.session_state:
        st.markdown("---")
        st.subheader("\U0001F4E5 Export")

        col_bcf, col_json = st.columns(2)

        with col_bcf:
            bcf_issues = st.session_state.get("last_bcf_issues", [])
            ifc_file = st.session_state.get("last_ifc_file")
            if bcf_issues:
                try:
                    bcf_file = BcfXml.create_new("JM IDS Check")
                    for issue in bcf_issues:
                        topic = bcf_file.add_topic(
                            title=issue["title"],
                            description=issue["description"],
                            author="bim@jm.se",
                            topic_type="Error",
                            topic_status="Open",
                        )
                        if issue["guids"]:
                            try:
                                add_bcf_viewpoint(topic, issue, ifc_file)
                            except Exception:
                                pass
                    bcf_path = tempfile.mktemp(suffix=".bcf")
                    bcf_file.save(bcf_path)
                    with open(bcf_path, "rb") as f:
                        bcf_bytes = f.read()
                    os.unlink(bcf_path)
                    ts = datetime.now().strftime('%Y%m%d_%H%M')
                    st.download_button(
                        "\U0001F4CB Download BCF",
                        data=bcf_bytes,
                        file_name=f"ids_check_{st.session_state.last_filename}_{ts}.bcf",
                        mime="application/octet-stream",
                    )
                    st.caption(f"{len(bcf_issues)} issues")
                except Exception as e:
                    st.error(f"BCF export failed: {e}")
            else:
                st.info("No failures — no BCF needed.")

        with col_json:
            export = {
                "file": st.session_state.last_filename,
                "timestamp": datetime.now().isoformat(),
                "results": st.session_state.last_results,
            }
            ts = datetime.now().strftime('%Y%m%d_%H%M')
            st.download_button(
                "\U0001F4C4 Download JSON",
                data=json.dumps(export, indent=2, ensure_ascii=False),
                file_name=f"ids_check_{st.session_state.last_filename}_{ts}.json",
                mime="application/json",
            )


if __name__ == "__main__":
    main()
