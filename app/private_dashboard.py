import json
import os
import queue
import tempfile
import threading
import time

import streamlit as st

from app.private_automation import InstagramBot, compare_follow_data, load_instagram_data_from_zip


SETTINGS_FILE = "private_web_settings.json"


def load_settings():
    if not os.path.exists(SETTINGS_FILE):
        return {
            "min_wait": 30,
            "max_wait": 60,
            "manual_batch_size": 20,
        }
    try:
        with open(SETTINGS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {
            "min_wait": 30,
            "max_wait": 60,
            "manual_batch_size": 20,
        }


def save_settings(data):
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def ensure_state():
    defaults = {
        "unfollowers": [],
        "fans": [],
        "selected": [],
        "zip_info": "",
        "job_running": False,
        "job_type": "",
        "job_queue": queue.Queue(),
        "stop_event": None,
        "logs": [],
        "job_status": "",
    }
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def append_log(message):
    ts = time.strftime("%H:%M:%S")
    st.session_state.logs.append(f"[{ts}] {message}")
    if len(st.session_state.logs) > 300:
        st.session_state.logs = st.session_state.logs[-300:]


def process_job_events():
    job_queue = st.session_state.job_queue
    while True:
        try:
            event_type, payload = job_queue.get_nowait()
        except queue.Empty:
            break

        if event_type == "log":
            append_log(payload)
        elif event_type == "status":
            st.session_state.job_status = payload
            append_log(payload)
        elif event_type == "error":
            st.session_state.job_status = f"Failed: {payload}"
            append_log(f"Error: {payload}")
        elif event_type == "done":
            st.session_state.job_running = False
            st.session_state.job_type = ""
            st.session_state.stop_event = None


def start_auto_job(users, min_wait, max_wait):
    if st.session_state.job_running:
        st.warning("A job is already running.")
        return

    stop_event = threading.Event()
    st.session_state.stop_event = stop_event
    st.session_state.job_running = True
    st.session_state.job_type = "auto"
    st.session_state.job_status = "Auto run is starting..."
    job_queue = st.session_state.job_queue

    def worker():
        try:
            bot = InstagramBot()
            bot.run(
                users,
                min_wait=min_wait,
                max_wait=max_wait,
                logger=lambda msg: job_queue.put(("log", msg)),
                should_stop=lambda: stop_event.is_set(),
                show_dialog=False,
            )
            if stop_event.is_set():
                job_queue.put(("status", "Auto run stopped by user."))
            else:
                job_queue.put(("status", "Auto run completed."))
        except Exception as e:
            job_queue.put(("error", str(e)))
        finally:
            job_queue.put(("done", None))

    threading.Thread(target=worker, daemon=True).start()


def start_manual_job(users, batch_size):
    if st.session_state.job_running:
        st.warning("A job is already running.")
        return

    st.session_state.job_running = True
    st.session_state.job_type = "manual"
    st.session_state.job_status = "Manual mode is starting..."
    job_queue = st.session_state.job_queue

    def worker():
        try:
            bot = InstagramBot()
            bot.run_manual(
                users,
                batch_size=batch_size,
                logger=lambda msg: job_queue.put(("log", msg)),
            )
            job_queue.put(("status", "Manual mode completed."))
        except Exception as e:
            job_queue.put(("error", str(e)))
        finally:
            job_queue.put(("done", None))

    threading.Thread(target=worker, daemon=True).start()


st.set_page_config(page_title="Private Instagram Follow Manager", page_icon="IFM", layout="wide")
ensure_state()
process_job_events()

saved = load_settings()

st.title("Private Instagram Manager")
st.caption("Local dashboard: upload Instagram ZIP, select accounts, then run auto/manual mode on your machine.")

with st.expander("Last used settings", expanded=True):
    c1, c2, c3 = st.columns(3)
    min_wait = c1.number_input("Min wait (sec)", min_value=1, max_value=300, value=int(saved.get("min_wait", 30)), step=1)
    max_wait = c2.number_input("Max wait (sec)", min_value=1, max_value=600, value=int(saved.get("max_wait", 60)), step=1)
    manual_batch_size = c3.number_input("Manual batch size", min_value=1, max_value=100, value=int(saved.get("manual_batch_size", 20)), step=1)

    if min_wait > max_wait:
        st.warning("Min wait should be <= Max wait")

    if st.button("Save settings"):
        save_settings({
            "min_wait": int(min_wait),
            "max_wait": int(max_wait),
            "manual_batch_size": int(manual_batch_size),
        })
        st.success("Settings saved")

uploaded_zip = st.file_uploader(
    "Upload Instagram ZIP",
    type=["zip"],
    help="Use the original ZIP file downloaded from Instagram."
)

if uploaded_zip is not None:
    with st.spinner("Reading ZIP and extracting account lists..."):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".zip") as tmp_file:
            tmp_file.write(uploaded_zip.getvalue())
            tmp_path = tmp_file.name

        try:
            followers_data, following_data, followers_files, following_file = load_instagram_data_from_zip(tmp_path)
            followers_set, following_set, unfollowers, fans = compare_follow_data(followers_data, following_data)

            st.session_state.unfollowers = unfollowers
            st.session_state.fans = fans
            st.session_state.zip_info = (
                f"Followers files: {len(followers_files)} | Following file: {following_file}"
            )

            c1, c2, c3 = st.columns(3)
            c1.metric("Following", len(following_set))
            c2.metric("Followers", len(followers_set))
            c3.metric("Not Following Back", len(unfollowers))

            st.success("ZIP analyzed successfully")
            st.caption(st.session_state.zip_info)
        except Exception as e:
            st.session_state.unfollowers = []
            st.session_state.fans = []
            st.session_state.selected = []
            st.error(f"Failed to read ZIP: {e}")

tab_unfollowers, tab_fans = st.tabs(["Not Following Back", "I Don't Follow Back"])

with tab_unfollowers:
    st.write("Select users for automation")
    selected_unfollowers = st.multiselect(
        "User list",
        options=st.session_state.unfollowers,
        default=st.session_state.selected,
        key="selected_unfollowers"
    )
    st.session_state.selected = selected_unfollowers

with tab_fans:
    st.write("This list is for review. Auto mode should stay on Not Following Back only.")
    st.dataframe(
        {"username": st.session_state.fans},
        use_container_width=True,
        height=320
    )

st.divider()
st.subheader("Run Automation")

selected_users = st.session_state.selected
st.write(f"Selected users: {len(selected_users)}")

if st.session_state.job_running:
    st.info(f"Running: {st.session_state.job_type.upper()} | {st.session_state.job_status}")
else:
    if st.session_state.job_status:
        st.success(st.session_state.job_status)

col_auto, col_manual, col_stop = st.columns(3)

with col_auto:
    auto_clicked = st.button(
        "Start Auto Unfollow",
        type="primary",
        use_container_width=True,
        disabled=st.session_state.job_running,
    )

with col_manual:
    manual_clicked = st.button(
        "Start Manual Mode",
        use_container_width=True,
        disabled=st.session_state.job_running,
    )

with col_stop:
    stop_clicked = st.button(
        "Stop Auto",
        use_container_width=True,
        disabled=(not st.session_state.job_running or st.session_state.job_type != "auto"),
    )

if auto_clicked:
    if not selected_users:
        st.warning("Please select at least one user.")
    elif min_wait > max_wait:
        st.warning("Please fix wait range first.")
    else:
        start_auto_job(selected_users, int(min_wait), int(max_wait))

if manual_clicked:
    if not selected_users:
        st.warning("Please select at least one user.")
    else:
        start_manual_job(selected_users, int(manual_batch_size))

if stop_clicked and st.session_state.stop_event is not None:
    st.session_state.stop_event.set()
    st.session_state.job_status = "Stop requested..."
    append_log("Stop requested by user.")

st.subheader("Live Log")
log_text = "\n".join(st.session_state.logs[-120:])
st.text_area("Automation logs", value=log_text, height=280, disabled=True)

if st.session_state.job_running:
    time.sleep(1)
    st.rerun()
