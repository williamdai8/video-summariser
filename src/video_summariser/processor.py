import shutil
import subprocess
import time
import random
import json
import logging
from multiprocessing import current_process
from pathlib import Path
from typing import List, Tuple, Optional, Dict, Any

import imageio_ffmpeg

class ConfigManager:
    """Loads and validates configuration from JSON."""
    def __init__(self, config_path: str = "config.json"):
        self.path = Path(config_path)
        self.data = self._load()
        
    def _load(self) -> Dict:
        if not self.path.exists():
            raise FileNotFoundError(f"Config file not found: {self.path.absolute()}")
        with open(self.path, "r") as f:
            return json.load(f)

    @property
    def dirs(self) -> Dict[str, Path]:
        """Returns Path objects for all configured directories."""
        d = self.data["directories"]
        return {
            "logs": Path(d["logs"]),
            "video_out": Path(d["video_output"]),
            "image_out": Path(d["image_output"]),
            "temp_cli": Path(d["temp_cli"]),
            "temp_web": Path(d["temp_web"]),
            "temp_upload": Path(d["temp_upload"])
        }

    @property
    def defaults(self) -> Dict[str, Any]:
        return self.data["defaults"]

def setup_logging(config: ConfigManager, log_filename: str = "app.log"):
    """Configures logging based on JSON settings."""
    log_dir = config.dirs["logs"]
    log_dir.mkdir(parents=True, exist_ok=True)
    
    log_path = log_dir / log_filename
    
    logging.basicConfig(
        level=getattr(logging, config.data["logging"].get("level", "INFO")),
        format=config.data["logging"].get("format"),
        handlers=[
            logging.FileHandler(log_path, mode='a', encoding='utf-8'),
            logging.StreamHandler()
        ]
    )
    return log_path

class VideoProcessor:
    def __init__(self, temp_dir: Path):
        self.base_dir = temp_dir
        self.split_dir = self.base_dir / "splits"
        self.proc_dir = self.base_dir / "processed"
        self._ensure_dirs()

    def _ensure_dirs(self):
        for d in [self.split_dir, self.proc_dir]:
            if d.exists():
                shutil.rmtree(d)
            d.mkdir(parents=True, exist_ok=True)

    def cleanup(self):
        if self.base_dir.exists():
            shutil.rmtree(self.base_dir)

    @staticmethod
    def get_ffmpeg_exe() -> str:
        return imageio_ffmpeg.get_ffmpeg_exe()

    def split_video(self, input_path: Path, chunk_size_sec: int) -> List[Path]:
        logging.info(f"Splitting video: {input_path}")
        output_pattern = self.split_dir / "chunk_%03d.mp4"
        
        cmd = [
            self.get_ffmpeg_exe(), "-y",
            "-i", str(input_path),
            "-c", "copy",
            "-map", "0",
            "-segment_time", str(chunk_size_sec),
            "-f", "segment",
            "-reset_timestamps", "1",
            str(output_pattern)
        ]
        
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        chunks = sorted(list(self.split_dir.glob("*.mp4")))
        logging.info(f"Split complete. Created {len(chunks)} chunks.")
        return chunks

    @staticmethod
    def _generate_filter_string(duration_sec: int, config: Dict[str, Any]) -> str:
        segments = []
        current_time = 0.0
        mode = config.get("mode", "fixed")

        # Logic remains the same, just cleaner injection
        if mode == "fixed":
            interval = config.get("interval", 10)
            clip_dur = config.get("duration", 1)
            while current_time < duration_sec:
                end = min(current_time + clip_dur, duration_sec)
                segments.append(f"between(t,{current_time:.2f},{end:.2f})")
                current_time += interval

        elif mode == "random":
            min_gap = config.get("min_interval", 5.0)
            max_gap = config.get("max_interval", 15.0)
            min_dur = config.get("min_duration", 1.0)
            max_dur = config.get("max_duration", 3.0)

            while current_time < duration_sec:
                gap = random.uniform(min_gap, max_gap)
                current_time += gap
                if current_time >= duration_sec: break
                
                clip_len = random.uniform(min_dur, max_dur)
                end = min(current_time + clip_len, duration_sec)
                segments.append(f"between(t,{current_time:.2f},{end:.2f})")
                current_time += clip_len

        elif mode == "coverage":
            coverage = config.get("coverage", 0.2)
            coverage = max(0.01, min(0.99, coverage))
            min_dur = config.get("min_duration", 1.0)
            max_dur = config.get("max_duration", 3.0)
            gap_multiplier = (1.0 / coverage) - 1.0

            while current_time < duration_sec:
                clip_len = random.uniform(min_dur, max_dur)
                ideal_gap = clip_len * gap_multiplier
                jitter = random.uniform(0.8, 1.2)
                actual_gap = ideal_gap * jitter
                current_time += actual_gap
                if current_time >= duration_sec: break
                end = min(current_time + clip_len, duration_sec)
                segments.append(f"between(t,{current_time:.2f},{end:.2f})")
                current_time += clip_len

        return "+".join(segments) if segments else "between(t,0,0.1)"

    @staticmethod
    def process_chunk(args: Tuple) -> Tuple[bool, Optional[Path], str]:
        input_path, output_dir, chunk_duration, config, save_images, image_out_dir = args
        process_name = current_process().name
        filename = input_path.name
        output_path = output_dir / f"proc_{filename}"
        
        select_str = VideoProcessor._generate_filter_string(chunk_duration, config)
        
        video_filter = f"select='{select_str}',setpts=N/FRAME_RATE/TB"
        audio_filter = f"aselect='{select_str}',asetpts=N/SR/TB"

        cmd = [
            VideoProcessor.get_ffmpeg_exe(), "-y",
            "-i", str(input_path),
            "-vf", video_filter,
            "-af", audio_filter,
            "-c:v", "libx264",
            "-preset", "ultrafast",
            "-c:a", "aac",
            "-loglevel", "error",
            str(output_path)
        ]

        try:
            subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
            
            if save_images and image_out_dir:
                img_pattern = image_out_dir / f"{input_path.stem}_img_%03d.jpg"
                img_cmd = [
                    VideoProcessor.get_ffmpeg_exe(), "-y",
                    "-i", str(output_path),
                    "-vf", "fps=1",
                    "-q:v", "2",
                    "-loglevel", "error",
                    str(img_pattern)
                ]
                subprocess.run(img_cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)

            return True, output_path, f"[{process_name}] processed {filename}"
        except Exception as e:
            return False, None, f"[{process_name}] Failed {filename}: {str(e)}"

    def stitch_videos(self, files: List[Path], output_path: Path) -> Path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        list_file = self.base_dir / "concat_list.txt"
        with open(list_file, "w") as f:
            for path in files:
                clean_path = path.absolute().as_posix()
                f.write(f"file '{clean_path}'\n")

        cmd = [
            self.get_ffmpeg_exe(), "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output_path)
        ]
        
        subprocess.run(cmd, check=True, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        return output_path