"""
DirectShow バックエンドを用いた録画アプリ (GUI、MP4対応、品質ベース、録画時間指定、設定画面表示)

依存関係:
  - Python3
  - OpenCV (cv2)
    pip install opencv-python
  - VidGear
    pip install vidgear
  - Tkinter (標準ライブラリ)
  - Pillow
    pip install pillow

使い方:
  python record.py
"""

import sys

import cv2
from colorama import Fore, Style, init

init()
import ctypes
import datetime
import os
import pathlib
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

from PIL import Image, ImageTk
from vidgear.gears import CamGear, WriteGear

# 定数
PREVIEW_WIDTH = 1280
PREVIEW_HEIGHT = 720
EXT = ".mp4"
DEFAULT_SAVE_DIR = "recordings"
SAVE_DIR = os.path.abspath(DEFAULT_SAVE_DIR)
os.makedirs(SAVE_DIR, exist_ok=True)

# ANSIカラー付きログ出力関数
COLOR_MAP = {
    "[info]": Fore.LIGHTWHITE_EX,
    "[warning]": Fore.LIGHTYELLOW_EX,
    "[error]": Fore.LIGHTRED_EX,
    "[debug]": Fore.LIGHTCYAN_EX,
}

RESET_COLOR = Style.RESET_ALL


def print_color(msg):
    for level, color in COLOR_MAP.items():
        if msg.startswith(level):
            print(
                f"{color}{msg}{RESET_COLOR}",
                file=sys.stderr if level == "[error]" else sys.stdout,
            )
            return
    print(msg)


def get_windows_scaling():
    try:
        ctypes.windll.shcore.SetProcessDpiAwareness(0)  # DPI無視
        return 2  # 常に等倍
    except Exception:
        return 2


class RecorderApp(tk.Tk):
    def update_resolution_list(self):
        selected_name = self.device_menu.get()
        print_color(f"[info] {selected_name} を選択")
        devices = self.detect_devices()
        try:
            idx = devices.index(selected_name)
        except ValueError:
            messagebox.showerror("エラー", "選択されたデバイスが見つかりません。")
            print_color("[error] デバイスが見つかりません")
            resolutions = []
        else:
            resolutions = self.get_supported_resolutions(idx)

        self.resolution_menu["values"] = [
            f"{w}x{h}@{fps}fps" for w, h, fps in resolutions
        ]

        if resolutions:
            self.resolution_menu.current(0)
            print_color(
                f"[info] 解像度候補リストを初期化: {self.resolution_menu.get()}"
            )

        if hasattr(self, "start_btn"):
            self.start_btn.config(state=tk.NORMAL if resolutions else tk.DISABLED)
        if hasattr(self, "preview_btn"):
            self.preview_btn.config(state=tk.NORMAL if resolutions else tk.DISABLED)

    def get_supported_resolutions(self, device_index=0):
        print_color("[info] 解像度とFPSの取得中...")
        ffmpeg_cmd = RecorderApp.get_ffmpeg_path()
        devices = self.detect_devices()
        if device_index >= len(devices):
            return []
        device_name = devices[device_index]
        try:
            result = subprocess.run(
                [
                    ffmpeg_cmd,
                    "-hide_banner",
                    "-f",
                    "dshow",
                    "-list_options",
                    "true",
                    "-i",
                    f"video={device_name}",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                check=False,
            )
            lines = result.stderr.splitlines()
            supported = []
            has_mjpeg = any("vcodec=mjpeg" in line for line in lines)
            if not has_mjpeg:
                raise RuntimeError("このデバイスは MJPEG に対応していません")

            for line in lines:
                if "vcodec=mjpeg" in line and "fps=" in line:
                    match = re.search(r"max s=(\d+)x(\d+)\s+fps=(\d+)", line)
                    if match:
                        w, h, fps = map(int, match.groups())
                        supported.append((w, h, fps))

            if supported:
                print_color("[info] 取得完了！")
            return supported
        except Exception as e:
            print_color(f"[error] 解像度検出エラー: {e}")

        print_color("[warning] FFmpeg取得失敗、未対応のカメラです")
        return []

    def update_device_list(self):

        self.devices = self.detect_devices()
        self.device_menu["values"] = self.devices
        if self.devices:
            self.device_index.set(self.devices[0])
            print_color(f"[info] デバイスリスト更新: {self.devices}")

    @staticmethod
    def get_ffmpeg_path() -> str:

        if not hasattr(RecorderApp, "_ffmpeg_path"):
            RecorderApp._ffmpeg_path = None
            RecorderApp._ffmpeg_logged = False

            env_path = os.environ.get("FFMPEG_PATH")
            if env_path and os.path.exists(env_path):
                RecorderApp._ffmpeg_path = env_path
                log_src = "env"
            else:
                which = shutil.which("ffmpeg.exe") or shutil.which("ffmpeg")
                if which:
                    RecorderApp._ffmpeg_path = which
                    log_src = "PATH"
                elif getattr(sys, "frozen", False):
                    bundled = os.path.join(sys._MEIPASS, "ffmpeg.exe")
                    if os.path.exists(bundled):
                        RecorderApp._ffmpeg_path = bundled
                        log_src = "bundled"
                else:
                    local = pathlib.Path(__file__).with_name("ffmpeg.exe")
                    if local.exists():
                        RecorderApp._ffmpeg_path = str(local)
                        log_src = "local"

            if RecorderApp._ffmpeg_path:
                print_color(
                    f"[info] ffmpeg path ({log_src}) = {RecorderApp._ffmpeg_path}"
                )
            else:
                print_color("[error] ffmpeg が見つかりません")

        return RecorderApp._ffmpeg_path

    @staticmethod
    def select_codec():
        preferred_codec = "h264_qsv"
        fallback_codec = "libx264"
        ffmpeg_cmd = RecorderApp.get_ffmpeg_path()

        # コーデックリストに h264_qsv が存在するか確認
        try:
            result = subprocess.run(
                [ffmpeg_cmd, "-hide_banner", "-encoders"],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                encoding="utf-8",
                check=True,
            )
            encoder_list = result.stdout.splitlines()
            if not any(preferred_codec in line for line in encoder_list):
                raise RuntimeError("h264_qsv not in encoder list")
        except Exception as e:
            print_color(f"[warning] h264_qsv未検出: {e}")
            print_color(f"[warning] fallback to {fallback_codec}")
            return fallback_codec

        # 実行テスト（2フレームの黒映像をエンコード）
        try:
            with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmpfile:
                test_output = tmpfile.name

            test_cmd = [
                ffmpeg_cmd,
                "-f",
                "lavfi",
                "-i",
                "color=black:s=128x128:d=0.1:r=30",  # 3フレーム (0.1秒)
                "-vcodec",
                preferred_codec,
                "-t",
                "0.1",  # 時間制限
                "-y",
                test_output,
            ]
            subprocess.run(
                test_cmd,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=True,
            )

            if os.path.exists(test_output) and os.path.getsize(test_output) > 0:
                print_color(f"[info] ハードウェアエンコード確認済み: {preferred_codec}")
                os.remove(test_output)
                return preferred_codec
            else:
                raise RuntimeError("Output file not created")

        except Exception as e:
            print_color(f"[warning] h264_qsv 実行失敗: {e}")
            print_color(f"[warning] fallback to {fallback_codec}")
            return fallback_codec

    def detect_devices(self):

        ffmpeg_cmd = RecorderApp.get_ffmpeg_path()  # ffmpegパスを取得
        try:
            result = subprocess.run(
                [
                    ffmpeg_cmd,
                    "-hide_banner",
                    "-f",
                    "dshow",
                    "-list_devices",
                    "true",
                    "-i",
                    "dummy",
                ],
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                encoding="utf-8",
                check=True,
            )
            lines = result.stderr.splitlines()
            devices = []
            for line in lines:
                if "(video)" in line and '"' in line:
                    name = line.split('"')[1]
                    devices.append(name)
            if not devices:
                devices = ["Default Camera"]
            return devices
        except Exception as e:
            print_color(f"[error] Device detection failed: {e}")
            return ["Default Camera"]

    def __init__(self):
        # アプリ起動時にデフォルトデバイスを表示
        # self.CODEC = "libx264" # for test
        # self.CODEC = "h264_qsv" # for test
        self.CODEC = self.select_codec()
        devices = self.detect_devices()
        if devices:
            print_color(f"[info] アプリ起動時の選択デバイス: {devices[0]}")
        super().__init__()

        # DPIスケーリング設定
        scale = get_windows_scaling()
        self.tk.call("tk", "scaling", scale)

        # スクリーンサイズを取得してスケーリングを考慮したウィンドウサイズに設定
        screen_width = self.winfo_screenwidth()
        screen_height = self.winfo_screenheight()

        # 横幅が1920を超える場合は制限
        max_width = 1800
        if screen_width > max_width:
            screen_width = max_width
        max_height = 960
        if screen_height > max_height:
            screen_height = max_height

        self.geometry(f"{screen_width}x{screen_height}")

        self.title("録画アプリ")
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self.device_index = tk.IntVar(value=0)
        # self.width = tk.IntVar(value=1280)
        # self.height = tk.IntVar(value=960)
        self.fps = tk.IntVar(value=30)
        self.duration = tk.IntVar(value=60)
        self.output = tk.StringVar()
        self.quality = tk.IntVar()
        self.quality_label = tk.StringVar(value=str(self.quality.get()))
        self.recording = False
        self.previewing = False
        self.stream = None
        self.writer = None
        self.latest_frame = None
        self.gray_mode = tk.BooleanVar(value=False)  # グレースケールモードのトグル
        # 先に None で初期化（UI構築前）
        self.start_btn = None
        self.preview_btn = None

        self.create_widgets()

        # UI構築後に解像度更新を遅延実行（ボタンの安全な制御が可能に）
        self.after(100, self.update_resolution_list)

    def update_device_status(self):
        devices = self.detect_devices()
        if devices and devices != ["Default Camera"]:
            self.device_status.config(text="デバイス検出済み", foreground="green")
        else:
            self.device_status.config(text="デバイス未検出", foreground="red")

    def create_widgets(self):
        frame = ttk.Frame(self, padding=10, width=320)
        frame.pack_propagate(False)  # 固定サイズにする
        frame.pack(side=tk.LEFT, fill=tk.Y)

        labels = ["デバイス番号:", "解像度:", "録画時間(s):"]
        vars_ = [self.device_index, None, self.duration]
        for i, (lbl, var) in enumerate(zip(labels, vars_)):
            ttk.Label(frame, text=lbl).grid(column=0, row=i, sticky=tk.W)
            if lbl == "デバイス番号:":
                device_frame = ttk.Frame(frame)
                device_frame.grid(column=1, row=i, columnspan=2, sticky=tk.W)
                self.device_index = tk.StringVar()
                self.device_menu = ttk.Combobox(
                    device_frame,
                    textvariable=self.device_index,
                    width=20,
                )
                self.device_menu["values"] = self.detect_devices()
                if self.device_menu["values"]:
                    self.device_menu.current(0)
                self.device_menu.pack(side=tk.LEFT)
                self.device_menu.bind(
                    "<<ComboboxSelected>>", lambda e: self.update_resolution_list()
                )
                ttk.Button(
                    device_frame, text="↻", command=self.update_device_list, width=2
                ).pack(side=tk.LEFT, padx=5)
            elif lbl == "解像度:":
                res_frame = ttk.Frame(frame)
                res_frame.grid(column=1, row=i, columnspan=2, sticky=tk.W)
                self.resolution_var = tk.StringVar()
                self.resolution_menu = ttk.Combobox(
                    res_frame, textvariable=self.resolution_var, width=20
                )
                resolutions = self.get_supported_resolutions()
                self.resolution_menu["values"] = [
                    f"{w}x{h}@{fps}fps" for w, h, fps in resolutions
                ]
                if resolutions:
                    self.resolution_menu.current(0)
                self.resolution_menu.pack(side=tk.LEFT)
                self.resolution_menu.bind(
                    "<<ComboboxSelected>>",
                    lambda e: print_color(
                        f"[info] 解像度選択: {self.resolution_var.get()}"
                    ),
                )
                ttk.Button(
                    res_frame, text="↻", command=self.update_resolution_list, width=2
                ).pack(side=tk.LEFT, padx=5)
            else:
                ttk.Entry(frame, textvariable=var, width=6).grid(column=1, row=i)

                # 品質スライダー（-crf / -global_quality をコーデックに応じて切替）
        self.quality_label_text = tk.StringVar(value="品質")
        ttk.Label(frame, textvariable=self.quality_label_text).grid(
            column=0, row=5, sticky=tk.W
        )
        self.quality_frame = ttk.Frame(frame)
        self.quality_frame.grid(column=1, row=5, columnspan=2, sticky=tk.EW)

        self.quality_slider_label = ttk.Label(self.quality_frame, text="低品質")
        self.quality_slider_label.pack(side=tk.LEFT)

        self.quality_scale = ttk.Scale(
            self.quality_frame,
            variable=self.quality,
            from_=0,
            to=51,
            orient=tk.HORIZONTAL,
        )
        self.quality_scale.pack(side=tk.LEFT, fill=tk.X, expand=True)

        self.quality_label_high = ttk.Label(self.quality_frame, text="高品質")
        self.quality_label_high.pack(side=tk.LEFT)

        self.quality_value_label = ttk.Label(
            self.quality_frame, text=str(self.quality.get())
        )
        self.quality_value_label.pack(side=tk.LEFT, padx=5)

        self.quality.set(23)
        self.quality_label.set(str(self.quality.get()))

        self.quality.trace_add(
            "write",
            lambda *args: self.quality_value_label.config(text=str(self.quality.get())),
        )

        # コーデックに応じたスライダー設定の切り替え
        if self.CODEC == "libx264":
            self.quality_label_text.set("品質 (-crf)")
            self.quality_slider_label.config(text="低品質")
            self.quality_label_high.config(text="高品質")
            self.quality_scale.config(from_=51, to=1)
            self.quality.set(23)
        elif self.CODEC == "h264_qsv":
            self.quality_label_text.set("品質 (-global_quality)")
            self.quality_slider_label.config(text="低品質")
            self.quality_label_high.config(text="高品質")
            self.quality_scale.config(from_=33, to=1)
            self.quality.set(23)

        # トグルボタンの追加（UI左パネルの末尾に配置するのが良い）
        gray_frame = ttk.Frame(frame)
        gray_frame.grid(column=0, row=12, columnspan=3, sticky=tk.W, pady=(5, 0))
        ttk.Checkbutton(
            gray_frame,
            text="グレースケールで録画",
            variable=self.gray_mode,
            onvalue=True,
            offvalue=False
        ).pack(side=tk.LEFT)

        # 保存フォルダ表示と開くボタン（パス表示を下に移動）
        folder_frame = ttk.Frame(frame)
        folder_frame.grid(column=0, row=6, columnspan=3, sticky=tk.W)
        ttk.Label(folder_frame, text="保存先フォルダ:").pack(side=tk.LEFT)
        self.save_dir_var = tk.StringVar(value=DEFAULT_SAVE_DIR)
        existing_dirs = [name for name in os.listdir(".") if os.path.isdir(name)]
        self.save_dir_menu = ttk.Combobox(
            folder_frame, textvariable=self.save_dir_var, values=existing_dirs, width=20
        )
        self.save_dir_menu.pack(side=tk.LEFT, padx=5)
        ttk.Button(folder_frame, text="開く", command=self.open_folder, width=4).pack(
            side=tk.LEFT, padx=5
        )
        ttk.Button(
            folder_frame, text="↻", command=self.refresh_folder_list, width=2
        ).pack(side=tk.LEFT, padx=5)

        btn_frame = ttk.Frame(frame)
        btn_frame.grid(column=0, row=8, columnspan=3, pady=10)
        self.preview_btn = ttk.Button(
            btn_frame, text="プレビュー開始", command=self.toggle_preview
        )
        self.start_btn = ttk.Button(
            btn_frame, text="録画開始", command=self.start_record
        )
        self.stop_btn = ttk.Button(
            btn_frame, text="録画停止", command=self.stop_record, state=tk.DISABLED
        )
        self.preview_btn.pack(side=tk.LEFT, padx=5)
        self.start_btn.pack(side=tk.LEFT, padx=5)
        self.stop_btn.pack(side=tk.LEFT)

        ttk.Label(frame, text="使用コーデック:").grid(column=0, row=9, sticky=tk.W)
        ttk.Label(frame, text=self.CODEC).grid(
            column=1, row=9, columnspan=2, sticky=tk.W
        )

        ttk.Label(frame, text="残り時間(s):").grid(column=0, row=10, sticky=tk.W)
        self.timer_label = ttk.Label(
            frame, text="", font=("Helvetica", 16, "bold"), foreground="red"
        )
        self.timer_label.grid(column=1, row=10, columnspan=2, sticky=tk.W)

        status_frame = ttk.LabelFrame(frame, text="ステータス", padding=10)
        status_frame.grid(column=0, row=11, columnspan=3, sticky=tk.EW, pady=(10, 0))

        self.recording_status = ttk.Label(
            status_frame,
            text="待機中",
            font=("Helvetica", 14, "bold"),
            foreground="gray",
        )
        self.device_status = ttk.Label(
            status_frame,
            text="デバイス未検出",
            font=("Helvetica", 10),
            foreground="gray",
        )
        self.preview_status = ttk.Label(
            status_frame,
            text="プレビュー停止中",
            font=("Helvetica", 12, "bold"),
            foreground="gray",
        )

        self.recording_status.pack(anchor=tk.W)
        self.device_status.pack(anchor=tk.W, pady=(2, 0))
        self.preview_status.pack(anchor=tk.W)
        self.update_device_status()

        self.preview_canvas = tk.Canvas(
            self, width=PREVIEW_WIDTH, height=PREVIEW_HEIGHT, bg="black"
        )
        self.preview_canvas.pack(side=tk.RIGHT)

    def toggle_preview(self):
        if self.previewing:
            self.stop_preview()
        else:
            self.start_preview()

    def start_preview(self):
        selected_name = self.device_menu.get()
        devices = getattr(self, "devices", []) or self.detect_devices()
        try:
            idx = devices.index(selected_name)
        except ValueError:
            messagebox.showerror("エラー", "選択されたデバイスが見つかりません。")
            print_color("[error] デバイスが見つかりません")
            return

        res_text = self.resolution_var.get()
        try:
            size, fps_text = res_text.split("@")
            w, h = map(int, size.split("x"))
            fps = int(fps_text.replace("fps", ""))
            self.fps.set(fps)
        except Exception:
            w, h = 640, 480  # fallback

        cam_options = {
            "CAP_PROP_FRAME_WIDTH": w,
            "CAP_PROP_FRAME_HEIGHT": h,
            "CAP_PROP_FPS": fps,
            "CAP_PROP_FOURCC": cv2.VideoWriter_fourcc(*"MJPG"),
            "CAP_PROP_SETTINGS": 1,
            "THREADED_QUEUE_MODE": True,
            "logging": False,
        }
        self.stream = CamGear(source=idx, backend=cv2.CAP_DSHOW, **cam_options).start()
        self.previewing = True
        self.preview_btn.config(text="プレビュー停止")
        self.preview_status.config(text="● プレビュー中", foreground="blue")
        self.preview_blink = True
        self.blink_preview_label()

        # アスペクト比に応じてCanvasサイズを更新
        aspect_ratio = w / h
        canvas_width = PREVIEW_WIDTH
        canvas_height = int(canvas_width / aspect_ratio)
        self.preview_canvas.config(width=canvas_width, height=canvas_height)

        threading.Thread(target=self.preview_loop, daemon=True).start()
        print_color(f"[info] プレビュー開始: {selected_name} ({w}x{h}@{fps}fps)")

    def preview_loop(self):
        while self.previewing:
            frame = self.stream.read()
            if frame is None:
                break

            if self.gray_mode.get():
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                frame = cv2.merge([gray, gray, gray])

            canvas_width = self.preview_canvas.winfo_width()
            canvas_height = self.preview_canvas.winfo_height()
            pv = cv2.resize(frame, (canvas_width, canvas_height))
            self.latest_frame = cv2.cvtColor(pv, cv2.COLOR_BGR2RGB)
            self.update_preview()


    def update_preview(self):
        if self.latest_frame is None:
            return
        img = ImageTk.PhotoImage(Image.fromarray(self.latest_frame))
        self.preview_canvas.create_image(0, 0, anchor=tk.NW, image=img)
        self.preview_canvas.image = img

    def stop_preview(self):
        self.previewing = False
        self.preview_btn.config(text="プレビュー開始")
        self.preview_status.config(text="プレビュー停止中", foreground="gray")
        self.preview_blink = False
        if self.stream:
            self.stream.stop()
            self.stream = None
        self.preview_canvas.delete("all")
        print_color("[info] プレビュー停止")

    def start_record(self):
        now = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

        # ユーザ指定のフォルダ名に対応（存在しなければ作成）
        target_dir = os.path.abspath(self.save_dir_var.get())
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)

        output_path = os.path.join(target_dir, f"{now}{EXT}")
        self.output.set(output_path)
        try:
            res_text = self.resolution_var.get()
            try:
                size, fps_text = res_text.split("@")
                w, h = map(int, size.split("x"))
                fps = int(fps_text.replace("fps", ""))
                self.fps.set(fps)
            except Exception:
                w, h = 640, 480  # fallback

            f, dur = self.fps.get(), self.duration.get()
            out = self.output.get().strip()
            quality = self.quality.get()
            if w <= 0 or h <= 0 or f <= 0 or dur <= 0 or not out.lower().endswith(EXT):
                raise ValueError
        except Exception:
            messagebox.showerror(
                "エラー",
                "パラメーターが不正です。数値とMP4ファイル名を確認してください。",
            )
            return
        options = {
            "-vcodec": self.CODEC,
            # "-crf": quality,
            # "-global_quality": quality,
            "-preset": "medium",
            "-pix_fmt": "yuv420p",
            "-movflags": "+faststart",
            "-input_framerate": f,
        }
        if self.CODEC == "libx264":
            # ソフトウェアエンコード用：CRF方式（品質重視）
            options["-crf"] = str(quality)
        elif self.CODEC == "h264_qsv":
            # ハードウェアエンコード用：global_quality または b:v
            options["-global_quality"] = str(quality)
        else:
            print_color(
                f"[warning] 未対応のコーデック: {self.CODEC}。デフォルト設定で進行"
            )

        if not self.previewing:
            self.start_preview()
        try:
            print_color(
                f"[info] 録画開始 codec={self.CODEC}, quality={quality}, fps={f},  out={out}"
            )
            self.writer = WriteGear(
                output=out, compression_mode=True, logging=False, **options
            )
        except Exception as e:
            messagebox.showerror("エラー", f"録画開始失敗：\n{e}")
            print_color("[error] 録画開始失敗")
            return
        self.recording = True
        self.remaining = dur
        self.recording_status.config(text="● 録画中", foreground="red")
        self.blink = True
        self.blink_recording_label()
        self.update_timer()
        self.start_btn.config(state=tk.DISABLED)
        self.stop_btn.config(state=tk.NORMAL)
        threading.Thread(target=self.record_loop, args=(w, h, dur), daemon=True).start()

    def record_loop(self, w, h, dur):
        start_time = time.time()
        while self.recording and time.time() - start_time < dur:
            frame = self.stream.read()
            if frame is None:
                break

            if self.gray_mode.get():
                gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                frame = cv2.merge([gray, gray, gray])

            self.writer.write(frame)
        self.stop_record()

    def refresh_folder_list(self):
        folders = [name for name in os.listdir(".") if os.path.isdir(name)]
        self.save_dir_menu["values"] = folders
        print_color(f"[info] フォルダリスト更新: {folders}")

    def stop_record(self):
        self.recording = False
        self.timer_label.config(text="")
        self.recording_status.config(text="待機中", foreground="gray")
        self.blink = False
        self.start_btn.config(state=tk.NORMAL)
        self.stop_btn.config(state=tk.DISABLED)
        if self.writer:
            self.writer.close()
        messagebox.showinfo("情報", "録画を停止しました。")
        print_color("[info] 録画停止")
        self.refresh_folder_list()

    def blink_recording_label(self):
        if getattr(self, "blink", False):
            current = self.recording_status.cget("foreground")
            new_color = "red" if current == "" else ""
            self.recording_status.config(foreground=new_color)
            self.after(500, self.blink_recording_label)

    def blink_preview_label(self):
        if getattr(self, "preview_blink", False):
            current = self.preview_status.cget("foreground")
            new_color = "blue" if current == "" else ""
            self.preview_status.config(foreground=new_color)
            self.after(500, self.blink_preview_label)

    def update_timer(self):
        if (
            self.recording
            and getattr(self, "remaining", None) is not None
            and self.remaining >= 0
        ):
            self.timer_label.config(text=str(self.remaining))
            self.remaining -= 1
            self.after(1000, self.update_timer)
        else:
            self.timer_label.config(text="")

    def open_folder(self):
        target_dir = os.path.abspath(self.save_dir_var.get())
        if not os.path.exists(target_dir):
            os.makedirs(target_dir, exist_ok=True)
            print_color(f"[info] フォルダ作成: {target_dir}")
        self.refresh_folder_list()
        subprocess.Popen(["explorer", target_dir], shell=True)

    def on_close(self):
        if self.recording:
            self.stop_record()
        if self.previewing:
            self.stop_preview()
        print_color("[info] アプリケーションを閉じます")
        self.destroy()


if __name__ == "__main__":
    RecorderApp().mainloop()
