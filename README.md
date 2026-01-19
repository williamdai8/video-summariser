# Video Summarizer

A high-performance Python tool that summarizes long videos by extracting short clips at regular intervals. It uses `ffmpeg` for processing and `multiprocessing` to speed up rendering by utilizing multiple CPU cores.

## Features

* **Parallel Processing**: Splits video into chunks and processes them on separate CPU cores.
* **CLI Interface**: Automate summarization via command line.
* **Web Interface**: User-friendly drag-and-drop interface powered by Streamlit.
* **Smart Stitching**: Automatically combines processed clips into a seamless summary.

## Installation

Requires Python 3.12+ and FFmpeg (installed automatically via `imageio-ffmpeg`).

```bash
# Clone the repository
git clone [https://github.com/yourusername/video-summarizer.git](https://github.com/yourusername/video-summarizer.git)
cd video-summariser

# Install dependencies
pip install -e .