import streamlit as st
import logging
from multiprocessing import cpu_count, Pool
from video_summariser.processor import VideoProcessor, ConfigManager, setup_logging

# --- Load Config ---
cfg = ConfigManager()
dirs = cfg.dirs
defaults = cfg.defaults

# --- Setup ---
st.set_page_config(page_title="Video Summarizer", layout="wide")
st.title("✂️ AI Video Summarizer")

log_file = setup_logging(cfg, "web_session.log")

# --- Sidebar ---
st.sidebar.header("Processing Mode")
mode = st.sidebar.radio("Mode", ("Fixed Interval", "Random Interval", "Target Coverage"), index=2)

config = {}
if mode == "Fixed Interval":
    config["mode"] = "fixed"
    config["interval"] = st.sidebar.slider("Interval (s)", 2, 60, defaults["interval"])
    config["duration"] = st.sidebar.slider("Clip Duration (s)", 1, 10, int(defaults["duration"]))
elif mode == "Random Interval":
    config["mode"] = "random"
    c1, c2 = st.sidebar.columns(2)
    config["min_interval"] = c1.number_input("Min Gap (s)", 2, 120, int(defaults["min_gap"]))
    config["max_interval"] = c2.number_input("Max Gap (s)", 2, 120, int(defaults["max_gap"]))
    c3, c4 = st.sidebar.columns(2)
    config["min_duration"] = c3.number_input("Min Clip (s)", 1.0, 10.0, float(defaults["min_clip"]))
    config["max_duration"] = c4.number_input("Max Clip (s)", 1.0, 10.0, float(defaults["max_clip"]))
elif mode == "Target Coverage":
    config["mode"] = "coverage"
    pct = st.sidebar.slider("Target Video %", 1, 100, defaults["coverage_percent"])
    config["coverage"] = pct / 100.0
    st.sidebar.info(f"Randomly selecting **{pct}%** of content.")
    c1, c2 = st.sidebar.columns(2)
    config["min_duration"] = c1.number_input("Min Clip (s)", 1.0, 10.0, float(defaults["min_clip"]))
    config["max_duration"] = c2.number_input("Max Clip (s)", 1.0, 10.0, float(defaults["max_clip"]))

st.sidebar.markdown("---")
save_images = st.sidebar.checkbox("Save Extracted Images", value=defaults["save_images"])
chunk_len = st.sidebar.number_input("Chunk Size (s)", value=defaults["chunk_size"])
cores = st.sidebar.slider("CPU Cores", 1, cpu_count(), max(1, cpu_count()-1))

# --- UI Logic ---
col1, col2 = st.columns([2, 1])

with col2:
    st.markdown("### 📜 Activity Log")
    log_area = st.empty()

def update_logs():
    if log_file.exists():
        with open(log_file, "r") as f:
            lines = f.readlines()
            log_area.code("".join(lines[-20:]), language="text")

with col1:
    uploaded_file = st.file_uploader("Upload Video", type=["mp4", "mov", "mkv"])

if uploaded_file:
    dirs["temp_upload"].mkdir(exist_ok=True)
    input_path = dirs["temp_upload"] / uploaded_file.name
    with open(input_path, "wb") as f:
        f.write(uploaded_file.getbuffer())

    original_name = input_path.stem
    final_output_file = dirs["video_out"] / f"{original_name}_short.mp4"
    
    img_output_path = None
    if save_images:
        img_output_path = dirs["image_out"] / original_name
        img_output_path.mkdir(parents=True, exist_ok=True)

    with col1:
        st.success(f"Loaded: {uploaded_file.name}")
        if st.button("🚀 Start Processing"):
            logging.info(f"Starting session for: {original_name}")
            update_logs()
            
            progress_bar = st.progress(0)
            status_text = st.empty()
            processor = VideoProcessor(dirs["temp_web"])

            try:
                status_text.text("Splitting video...")
                chunks = processor.split_video(input_path, chunk_len)
                update_logs()

                status_text.text(f"Processing on {cores} cores...")
                tasks = [(c, processor.proc_dir, chunk_len, config, save_images, img_output_path) for c in chunks]
                
                processed_files = []
                with Pool(processes=cores) as pool:
                    for i, res in enumerate(pool.imap_unordered(VideoProcessor.process_chunk, tasks)):
                        success, path, msg = res
                        if success:
                            processed_files.append(path)
                            logging.info(msg)
                        else:
                            logging.error(msg)
                        update_logs()
                        progress_bar.progress((i + 1) / len(tasks))

                if processed_files:
                    status_text.text("Stitching...")
                    processed_files.sort()
                    processor.stitch_videos(processed_files, final_output_file)
                    update_logs()
                    status_text.success("Complete!")
                    st.video(str(final_output_file))
                else:
                    st.error("Failed.")

            except Exception as e:
                logging.exception("Fatal error")
                st.error(f"Error: {e}")
            finally:
                if input_path.exists(): input_path.unlink()
                processor.cleanup()
                update_logs()