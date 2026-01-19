# Video Summariser

A high-performance Python tool that summarises long videos by extracting short clips using intelligent selection modes. It uses `ffmpeg` for video processing and `multiprocessing` to leverage multiple CPU cores for faster rendering.

## Features

* **Three Processing Modes**:
  * **Fixed Interval**: Selects clips at fixed intervals (e.g., 10 seconds apart, 1 second duration)
  * **Random Interval**: Randomly selects clips with variable gaps and durations within specified ranges
  * **Target Coverage**: Randomly selects clips to achieve a target coverage percentage of total video

* **Parallel Processing**: Splits video into chunks and processes them simultaneously across multiple CPU cores
* **Web Interface**: User-friendly drag-and-drop interface powered by Streamlit
* **CLI Interface**: Command-line tool for batch processing and automation
* **Smart Stitching**: Automatically combines processed clips into seamless summaries
* **Image Extraction**: Optional extraction of key frames from summarised video
* **Run Configuration Tracking**: Each run captures all settings in `run_config.json` for reproducibility
* **Per-Run Logging**: Isolated log file for each processing run

## Installation

Requires Python 3.12+, FFmpeg (installed automatically via `imageio-ffmpeg`) and uv for package management.

## 🚀 Installation & Setup using `uv`

This project uses [uv](https://github.com/astral-sh/uv), an extremely fast Python package installer and resolver.

### Install `uv`
If you haven't installed `uv` yet:
```bash
# MacOS / Linux
curl -LsSf [https://astral.sh/uv/install.sh](https://astral.sh/uv/install.sh) | sh

# Windows (PowerShell)
powershell -c "irm [https://astral.sh/uv/install.ps1](https://astral.sh/uv/install.ps1) | iex"

# Or via pip
pip install uv
```

```bash
# Clone the repository
git clone https://github.com/williamdai8/video-summariser.git
cd video-summariser
```

## Usage

### Web Interface

Run the interactive Streamlit application:

```bash
uv run streamlit run src/video_summariser/run_web.py
```

NOTE: POTENTIAL ERROR, HOW TO FIX!

```bash
warning: Failed to hardlink files; falling back to full copy. This may lead to degraded performance.
         If the cache and target directories are on different filesystems, hardlinking may not be supported.
         If this is intentional, set `export UV_LINK_MODE=copy` or use `--link-mode=copy` to suppress this warning.
error: Failed to install: pydeck-0.9.1-py2.py3-none-any.whl (pydeck==0.9.1)
  Caused by: failed to hardlink file from LOCATION\pydeck\bindings\base_map_provider.py to LOCATION\.venv\Lib\site-packages\pydeck\bindings\base_map_provider.py: The cloud operation cannot be performed on a file with incompatible hardlinks. (os error 396)
```

If you encounter the above error, run the below and hopefully be happy days:
```bash
set UV_LINK_MODE=copy
```

Then:
1. Upload a video file (MP4, MOV, or MKV)
2. Select a processing mode from the sidebar
3. Configure mode-specific parameters
4. (Optional) Enable "Save Extracted Images"
5. Click "🚀 Start Processing"
6. Watch the Magic Happen! distiling a 60 minute video down to your chosen duration in less than 3 minutes.

**Mode Details**:

- **Fixed Interval**: 
  - `Interval (s)`: Seconds between clip start points
  - `Clip Duration (s)`: Duration of each extracted clip

- **Random Interval**:
  - `Min Gap (s)`: Minimum seconds between clips
  - `Max Gap (s)`: Maximum seconds between clips
  - `Min Clip (s)`: Minimum clip duration
  - `Max Clip (s)`: Maximum clip duration

- **Target Coverage**:
  - `Target Video %`: Percentage of total video to include (1-100%)
  - `Min Clip (s)`: Minimum clip duration
  - `Max Clip (s)`: Maximum clip duration

### CLI Interface

Run from command line:

```bash
python src/video_summariser/cli.py <input_video> [options]
```

## Configuration

Edit `config.json` to customise defaults and directory paths:

```json
{
    "directories": {
        "base_output": "user_data",
        "logs": "user_data/logs",
        "video_output": "user_data/output/video",
        "image_output": "user_data/output/video_images",
        "temp_cli": "user_data/temp_cli_work",
        "temp_web": "user_data/temp_web_work",
        "temp_upload": "user_data/temp_web_upload"
    },
    "modes": {
        "fixed": {
            "label": "Fixed Interval",
            "description": "📍 Selecting clips at fixed intervals..."
        },
        "random": {
            "label": "Random Interval",
            "description": "🎲 Randomly selecting clips..."
        },
        "coverage": {
            "label": "Target Coverage",
            "description": "🎯 Randomly selecting clips to achieve target coverage..."
        }
    },
    "defaults": {
        "mode": "fixed",
        "chunk_sise": 120,
        "interval": 10,
        "duration": 1.0,
        "min_gap": 5.0,
        "max_gap": 20.0,
        "min_clip": 1.0,
        "max_clip": 3.0,
        "coverage_percent": 20,
        "save_images": false
    }
}
```

## Output Structure

Each processing run creates an organised folder with the following structure:

```
user_data/output/
  YYYYMMDD_HHMMSS_video_name/
    ├── run_config.json      # All settings used for this run
    ├── log.txt              # Processing log
    ├── video/
    │   └── video_name_short.mp4
    └── images/              # (optional, if enabled)
        ├── video_name_img_001.jpg
        ├── video_name_img_002.jpg
        └── ...
```

### run_config.json

Captures all processing parameters for reproducibility:

```json
{
  "timestamp": "20260119_143022",
  "video_name": "my_video",
  "video_filename": "my_video.mp4",
  "mode": "coverage",
  "settings": {
    "mode": "coverage",
    "coverage": 0.2
  },
  "chunk_size": 120,
  "save_images": false,
  "cpu_cores": 4
}
```

## Project Structure

```
video-summariser/
├── config.json              # Main configuration file
├── pyproject.toml           # Package metadata
├── README.md
└── src/
    └── video_summariser/
        ├── cli.py           # Command-line interface
        ├── processor.py     # Core video processing logic
        ├── run_web.py       # Streamlit web interface
        └── __pycache__/
└── user_data/               # All outputs stored here
    ├── logs/
    ├── temp_cli_work/
    ├── temp_web_work/
    ├── temp_web_upload/
    └── output/              # Final output runs
```

## How It Works

1. **Video Splitting**: Input video is split into manageable chunks
2. **Clip Selection**: Based on selected mode, clips are identified for inclusion
3. **Parallel Processing**: Each chunk is processed independently using ffmpeg filters
4. **Image Extraction**: (Optional) Key frames are extracted from processed chunks
5. **Stitching**: All processed clips are combined into the final summary video
6. **Cleanup**: Temporary files are automatically removed

## Temporary Folders

All temporary processing files are stored in `user_data/`:
- `temp_cli_work/`: Temporary files for CLI processing
- `temp_web_work/`: Temporary files for web processing
- `temp_web_upload/`: Uploaded video storage (cleaned after processing)

## Requirements

- Python 3.12+
- uv for package management
- FFmpeg (auto-installed via imageio-ffmpeg)
- Streamlit (for web interface)
- Additional dependencies: imageio-ffmpeg, streamlit

## License

MIT License
