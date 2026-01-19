import streamlit as st
import logging
import shutil
import json
from datetime import datetime
from pathlib import Path
from multiprocessing import cpu_count, Pool
from video_summariser.processor import VideoProcessor, ConfigManager, setup_logging

# --- Load Config ---
cfg = ConfigManager()
dirs = cfg.dirs
defaults = cfg.defaults
modes_info = cfg.data.get("modes", {})

# --- Setup ---
st.set_page_config(page_title="Video Summarier", layout="wide")
st.title("✂️ Video Summarizer")

# Ensure base output directory exists
dirs["video_out"].parent.mkdir(parents=True, exist_ok=True)

# --- Sidebar ---
st.sidebar.header("Processing Mode")
mode_options = (modes_info.get("fixed", {}).get("label", "Fixed Interval"),
                modes_info.get("random", {}).get("label", "Random Interval"),
                modes_info.get("coverage", {}).get("label", "Target Coverage"))
mode = st.sidebar.radio("Mode", mode_options, index=2)

config = {}
if mode == modes_info.get("fixed", {}).get("label", "Fixed Interval"):
    st.sidebar.info(modes_info.get("fixed", {}).get("description", ""))
    config["mode"] = "fixed"
    config["interval"] = st.sidebar.slider("Interval (s)", 2, 60, defaults["interval"])
    config["duration"] = st.sidebar.slider("Clip Duration (s)", 1, 10, int(defaults["duration"]))
elif mode == modes_info.get("random", {}).get("label", "Random Interval"):
    st.sidebar.info(modes_info.get("random", {}).get("description", ""))
    config["mode"] = "random"
    c1, c2 = st.sidebar.columns(2)
    config["min_interval"] = c1.number_input("Min Gap (s)", 2, 120, int(defaults["min_gap"]))
    config["max_interval"] = c2.number_input("Max Gap (s)", 2, 120, int(defaults["max_gap"]))
    c3, c4 = st.sidebar.columns(2)
    config["min_duration"] = c3.number_input("Min Clip (s)", 1.0, 10.0, float(defaults["min_clip"]))
    config["max_duration"] = c4.number_input("Max Clip (s)", 1.0, 10.0, float(defaults["max_clip"]))
elif mode == modes_info.get("coverage", {}).get("label", "Target Coverage"):
    st.sidebar.info(modes_info.get("coverage", {}).get("description", ""))
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

run_log_file = None

def update_logs():
    if run_log_file and run_log_file.exists():
        with open(run_log_file, "r", encoding="utf-8") as f:
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
    
    img_output_path = None
    if save_images:
        img_output_path = "placeholder"  # Will be set during processing

    with col1:
        st.success(f"Loaded: {uploaded_file.name}")
        if st.button("🚀 Start Processing"):
            # Create timestamped output folder and log file for this run
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            run_folder = dirs["video_out"].parent / f"{timestamp}_{original_name}"
            run_folder.mkdir(parents=True, exist_ok=True)
            
            video_output_folder = run_folder / "video"
            video_output_folder.mkdir(exist_ok=True)
            final_output_file = video_output_folder / f"{original_name}_short.mp4"
            
            if save_images:
                img_output_path = run_folder / "images"
                img_output_path.mkdir(exist_ok=True)
            
            # Create fresh run-specific log file
            run_log_file = run_folder / "log.txt"
            
            # Create run config file with all settings
            run_config = {
                "timestamp": timestamp,
                "video_name": original_name,
                "video_filename": uploaded_file.name,
                "mode": config.get("mode"),
                "settings": config,
                "chunk_size": chunk_len,
                "save_images": save_images,
                "cpu_cores": cores
            }
            run_config_file = run_folder / "run_config.json"
            with open(run_config_file, "w", encoding="utf-8") as f:
                json.dump(run_config, f, indent=2)
            
            # Clear existing handlers and configure logging for this run
            root_logger = logging.getLogger()
            for handler in root_logger.handlers[:]:
                root_logger.removeHandler(handler)
            
            # Add file handler for run-specific log
            file_handler = logging.FileHandler(run_log_file, mode='w', encoding='utf-8')
            file_handler.setFormatter(logging.Formatter('%(asctime)s [%(levelname)s] %(message)s'))
            root_logger.addHandler(file_handler)
            root_logger.setLevel(logging.INFO)
            
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
                if dirs["temp_upload"].exists(): 
                    shutil.rmtree(dirs["temp_upload"])
                update_logs()