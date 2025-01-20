import sys
import os
import random
import subprocess
import mimetypes

from PyQt5.QtCore import (
    Qt,
    QThread,
    pyqtSignal,
    QPoint
)
from PyQt5.QtGui import (
    QFont,
    QFontMetrics
)
from PyQt5.QtWidgets import (
    QApplication,
    QMainWindow,
    QWidget,
    QVBoxLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QListWidget,
    QAbstractItemView,
    QFileDialog,
    QSpinBox,
    QLineEdit,
    QMessageBox,
    QMenu,
    QProgressBar,
    QStyleFactory,
    QComboBox
)


FFMPEG_PATH = os.path.join('ffmpeg', 'bin', 'ffmpeg.exe')

FILTERS = {
    "No filter": '',
    "Random color shift": "eq=brightness={br}:contrast={ct}:saturation={sat},hue=h={hue}",
    "Black and white": "hue=s=0",
    "High contrast": "eq=contrast=2.0",
    "Low contrast": "eq=contrast=0.5",
    'Sepia': "colorchannelmixer=.393:.769:.189:0:.349:.686:.168:0:.272:.534:.131",
    'Inversion': "negate",
    "Blur (light)": "gblur=sigma=2",
    "Blur (strong)": "gblur=sigma=10",
    "Flip horizontally": "hflip",
    "Flip vertically": "vflip",
    "Pixelation": "scale=iw/10:ih/10,scale=iw*10:ih*10:flags=neighbor",
    "VHS": "chromashift=1:1,noise=alls=20:allf=t+u",
    "Blue Tones": "colorbalance=bs=1",
    "Red Tones": "colorbalance=rs=1",
    "Increased Brightness": "eq=brightness=0.2",
    "Decreased Brightness": "eq=brightness=-0.2",
    "Increased Saturation": "eq=saturation=2.0",
    "Decreased Saturation": "eq=saturation=0.5",
    "Green Tones": "colorbalance=gs=1",
    "Posterization": "pp=al",
    "Strong Sepia": "colorchannelmixer=.593:.869:.189:0:.649:.786:.268:0:.472:.734:.331",
    "Strong Red Tones": "colorbalance=rs=1",
    "Strong Green Tones": "colorbalance=gs=1",
    "Strong Blue Tones": "colorbalance=bs=1",
    "Warm Filter": "curves=r='0/0 0.4/0.5 1/1':g='0/0 0.6/0.6 1/1'",
    "Cool Filter": "curves=b='0/0 0.4/0.5 1/1':g='0/0 0.4/0.4 1/1'",
    "Bright and Saturated": "eq=brightness=0.3:saturation=2.0",
    "Grayish Tones": "eq=saturation=0.7:contrast=1.3",
    "Blue-Red": "colorchannelmixer=1:0:0:0:0:0:1:0:0:0:0:1",
    "Purple Tint": "colorbalance=rs=1.2:bs=1.2",
    "Random Filter": "RANDOM_PLACEHOLDER"
}

OVERLAY_POSITIONS = {
    "Top-Left": ("0", "0.07*main_h"),
    "Top-Center": ("(main_w-overlay_w)/2", "0.07*main_h"),
    "Top-Right": ("main_w-overlay_w", "0.07*main_h"),
    "Middle-Left": ("0", "(main_h-overlay_h)/2"),
    "Middle-Center": ("(main_w-overlay_w)/2", "(main_h-overlay_h)/2"),
    "Middle-Right": ("main_w-overlay_w", "(main_h-overlay_h)/2"),
    "Bottom-Left": ("0", "main_h-overlay_h"),
    "Bottom-Center": ("(main_w-overlay_w)/2", "main_h-overlay_h"),
    "Bottom-Right": ("main_w-overlay_w", "main_h-overlay_h")
}


def is_video_file(path):
    if not os.path.isfile(path):
        return False
    ext = os.path.splitext(path)[1].lower()
    known_ext = {'.mp4', '.mov', '.avi', '.mkv', '.flv', '.wmv', '.m4v'}
    if ext in known_ext:
        return True
    mime_type, _ = mimetypes.guess_type(path)
    return mime_type and mime_type.startswith('video')


def find_videos_in_folder(folder):
    found = []
    for root, dirs, files in os.walk(folder):
        for name in files:
            fp = os.path.join(root, name)
            if is_video_file(fp):
                found.append(fp)
    return found


def pick_random_filter():
    possible = [k for k in FILTERS.keys() if k not in ("Random filter", "No filter")]
    if not possible:
        return "No filter"
    return random.choice(possible)


def build_filter_chain(selected_filters):
    arr = []
    for f in selected_filters:

        if f == "Random filter":
            f = pick_random_filter()

        flt = FILTERS.get(f, "")
        if not flt:
            continue

        if f == "Random color shift":
            br = random.uniform(-0.1, 0.1)
            ct = random.uniform(0.8, 1.2)
            sat = random.uniform(0.8, 1.2)
            hue = random.uniform(-30, 30)
            flt = flt.format(
                br=f"{br:.2f}",
                ct=f"{ct:.2f}",
                sat=f"{sat:.2f}",
                hue=f"{hue:.2f}"
            )
        arr.append(flt)

    return ','.join(arr) if arr else ''


def build_scale_filter(scale_p):
    if scale_p == 100:
        return ''
    factor = scale_p / 100
    if factor > 1:

        return f"scale=iw*{factor}:ih*{factor},crop=iw/{factor}:ih/{factor}:(iw-iw/{factor})/2:(ih-ih/{factor})/2"
    else:

        return f"scale=iw*{factor}:ih*{factor},pad=iw/{factor}:ih/{factor}:(ow-iw)/2:(oh-ih)/2"


def build_ffmpeg_cmd(in_path, out_path, filters, scale_p, speed_p, overlay, overlay_pos):
    sp = speed_p / 100.0
    vf_parts = []

    chain = build_filter_chain(filters)

    scale_chain = build_scale_filter(scale_p)

    if chain and scale_chain:
        vf_parts.append(chain + ',' + scale_chain)
    elif chain:
        vf_parts.append(chain)
    elif scale_chain:
        vf_parts.append(scale_chain)

    joined = ",".join(vf_parts) if vf_parts else None

    cmd = [FFMPEG_PATH, '-y', '-i', in_path]

    use_overlay = False
    if overlay and os.path.isfile(overlay):
        use_overlay = True
        cmd += ['-i', overlay]

    fc_parts = []
    if joined:
        fc_parts.append(f"[0:v]{joined}[base]")
    else:

        fc_parts.append("[0:v]null[base]")

    if use_overlay:
        ox, oy = OVERLAY_POSITIONS.get(overlay_pos, ('0', '0'))

        fc_parts.append("[1:v]format=rgba[ovrl]")

        fc_parts.append(f"[base][ovrl]overlay=x={ox}:y={oy}[preSpeed]")

        fc_parts.append(f"[preSpeed]setpts=1/{sp}*PTS[vid]")
    else:
        fc_parts.append(f"[base]setpts=1/{sp}*PTS[vid]")

    fc_parts.append(f"[0:a]atempo={sp}[aud]")

    fc = '; '.join(fc_parts)

    cmd += [
        '-filter_complex', fc,
        '-map', '[vid]',
        '-map', '[aud]',
        '-c:v', 'libx264',
        '-crf', '23',
        '-c:a', 'aac',
        '-b:a', '192k',
        out_path
    ]
    return cmd


def process_ffmpeg(in_path, out_path, filters, scale_p, speed_p, overlay, overlay_pos):
    cmd = build_ffmpeg_cmd(in_path, out_path, filters, scale_p, speed_p, overlay, overlay_pos)

    if os.name == 'nt':

        CREATE_NO_WINDOW = 0x08000000
        subprocess.run(cmd, check=True, creationflags=CREATE_NO_WINDOW)
    else:
        subprocess.run(cmd, check=True)


class Worker(QThread):
    progress = pyqtSignal(int, int)
    finished = pyqtSignal()
    error = pyqtSignal(str)
    file_processing = pyqtSignal(str)

    def __init__(self, files, filters, scale, speed, overlay, out_dir, overlay_pos):
        super().__init__()
        self.files = files
        self.filters = filters
        self.scale = scale
        self.speed = speed
        self.overlay = overlay
        self.out_dir = out_dir
        self.overlay_pos = overlay_pos

    def run(self):
        total = len(self.files)
        for i, path_in in enumerate(self.files):
            try:
                base = os.path.basename(path_in)
                self.file_processing.emit(base)
                name, _ = os.path.splitext(base)
                out_path = os.path.join(self.out_dir, f"{name}_processed.mp4")

                process_ffmpeg(
                    path_in,
                    out_path,
                    self.filters,
                    self.scale,
                    self.speed,
                    self.overlay,
                    self.overlay_pos
                )
            except Exception as e:
                self.error.emit(str(e))
            self.progress.emit(i + 1, total)
        self.finished.emit()


class VideoUnicApp(QMainWindow):

    def __init__(self):
        super().__init__()
        self.setWindowTitle("Video Uniqueizer")
        self.setAcceptDrops(True)
        self.resize(1000, 600)

        self.main_w = QWidget()
        self.setCentralWidget(self.main_w)
        self.ly = QHBoxLayout()
        self.main_w.setLayout(self.ly)

        self.left_panel = QVBoxLayout()
        self.btn_add = QPushButton("Add video")
        self.btn_add.setMinimumHeight(40)
        self.btn_add.clicked.connect(self.on_add_files)
        self.left_panel.addWidget(self.btn_add)

        self.video_list = QListWidget()
        self.video_list.setSelectionMode(QAbstractItemView.ExtendedSelection)
        self.video_list.setContextMenuPolicy(Qt.CustomContextMenu)
        self.video_list.customContextMenuRequested.connect(self.on_list_menu)
        self.left_panel.addWidget(self.video_list)

        self.ly.addLayout(self.left_panel, 2)

        self.right_panel = QVBoxLayout()

        self.lbl_f = QLabel("Select filters:")
        self.filter_list = QListWidget()
        self.filter_list.setSelectionMode(QAbstractItemView.ExtendedSelection)

        for fn in FILTERS:
            self.filter_list.addItem(fn)
        self.filter_list.setFixedHeight(200)

        self.right_panel.addWidget(self.lbl_f)
        self.right_panel.addWidget(self.filter_list)

        row_scale = QHBoxLayout()
        row_scale.addWidget(QLabel("Scale (%)"))
        self.scale_spin = QSpinBox()
        self.scale_spin.setRange(10, 300)
        self.scale_spin.setValue(100)
        row_scale.addWidget(self.scale_spin)
        self.right_panel.addLayout(row_scale)

        row_speed = QHBoxLayout()
        row_speed.addWidget(QLabel("Speed (%)"))
        self.speed_spin = QSpinBox()
        self.speed_spin.setRange(50, 200)
        self.speed_spin.setValue(100)
        row_speed.addWidget(self.speed_spin)
        self.right_panel.addLayout(row_speed)

        row_overlay = QHBoxLayout()
        row_overlay.addWidget(QLabel("File Overlay:"))
        self.overlay_path = QLineEdit()
        btn_ol = QPushButton('Review...')
        btn_ol.clicked.connect(self.on_overlay)
        row_overlay.addWidget(self.overlay_path)
        row_overlay.addWidget(btn_ol)
        self.right_panel.addLayout(row_overlay)

        row_pos = QHBoxLayout()
        row_pos.addWidget(QLabel('Location:'))
        self.overlay_pos_combo = QComboBox()
        for pos in OVERLAY_POSITIONS:
            self.overlay_pos_combo.addItem(pos)
        row_pos.addWidget(self.overlay_pos_combo)
        self.right_panel.addLayout(row_pos)

        self.process_button = QPushButton('Process')
        self.process_button.clicked.connect(self.start_processing)
        self.right_panel.addWidget(self.process_button)

        self.progress_label = QLabel('')
        self.progress_bar = QProgressBar()
        self.progress_bar.setValue(0)
        self.right_panel.addWidget(self.progress_label)
        self.right_panel.addWidget(self.progress_bar)

        self.status_label = QLabel('')
        self.status_label.setWordWrap(False)
        self.right_panel.addWidget(self.status_label)
        self.right_panel.addStretch()

        self.ly.addLayout(self.right_panel, 1)

        self.setStyle(QStyleFactory.create('Fusion'))
        self.setStyleSheet("""
            QWidget {
                background-color: #2f2f2f;
                color: #e6e6e6;
                font-size: 13px;
            }
            QLineEdit {
                background-color: #3f3f3f;
                border: 1px solid #666;
                border-radius: 4px;
                padding: 4px;
            }
            QPushButton {
                background-color: #4d4d4d;
                border: 1px solid #777;
                border-radius: 4px;
                padding: 6px 12px;
            }
            QPushButton:hover {
                background-color: #5a5a5a;
            }
            QListWidget {
                background-color: #3f3f3f;
                border: 2px dashed #777;
            }
            QSpinBox {
                background-color: #3f3f3f;
                border: 1px solid #777;
                border-radius: 4px;
                padding: 4px;
                color: #fff;
            }
            QProgressBar {
                border: 1px solid #555;
                border-radius: 4px;
                text-align: center;
                background-color: #404040;
            }
            QProgressBar::chunk {
                background-color: #79a6d2;
            }
        """)

        def on_add_files(self):

            files, _ = QFileDialog.getOpenFileNames(
                self, "Select video", '',
                "Video files (*.mp4 *.mov *.avi *.mkv *.flv *.wmv *.m4v);;All files (*.*)"
            )
            for f in files:
                if is_video_file(f):
                    self.video_list.addItem(f)

        def on_list_menu(self, pos: QPoint):

            menu = QMenu()
            act_delete = menu.addAction("Delete selected")
            chosen = menu.exec_(self.video_list.viewport().mapToGlobal(pos))
            if chosen == act_delete:
                for it in self.video_list.selectedItems():
                    r = self.video_list.row(it)
                    self.video_list.takeItem(r)

        def on_overlay(self):

            fp, _ = QFileDialog.getOpenFileName(
                self, "Select an image or video to overlay", '',
                "Images/Videos (*.png *.jpg *.jpeg *.bmp *.mp4 *.mov *.avi *.mkv *.flv *.wmv *.m4v);;All files (*.*)"
            )
            if fp:
                self.overlay_path.setText(fp)

        def dragEnterEvent(self, e):

            if e.mimeData().hasUrls():
                e.acceptProposedAction()

        def dropEvent(self, e):

            for url in e.mimeData().urls():
                fp = url.toLocalFile()
                if os.path.isdir(fp):

                    vids = find_videos_in_folder(fp)
                    for v in vids:
                        self.video_list.addItem(v)
                else:

                    if is_video_file(fp):
                        self.video_list.addItem(fp)

        def start_processing(self):

            count = self.video_list.count()
            if count == 0:
                QMessageBox.warning(self, "No files", "Add files for processing.")
                return

            out_dir = QFileDialog.getExistingDirectory(self, "Select a folder to save to")
            if not out_dir:
                return

            sel_items = self.filter_list.selectedItems()
            selected_filters = [i.text() for i in sel_items]

            scale_val = self.scale_spin.value()
            speed_val = self.speed_spin.value()

            overlay_file = self.overlay_path.text().strip()
            overlay_file = overlay_file if overlay_file else None
            overlay_pos = self.overlay_pos_combo.currentText()

            files = []
            for i in range(count):
                files.append(self.video_list.item(i).text())

            self.thread = Worker(files, selected_filters, scale_val, speed_val, overlay_file, out_dir, overlay_pos)
            self.thread.progress.connect(self.on_prog)
            self.thread.finished.connect(self.on_done)
            self.thread.error.connect(self.on_err)
            self.thread.file_processing.connect(self.on_file_processing)

            self.progress_bar.setValue(0)
            self.progress_label.setText(f"0 / {count}")
            self.status_label.setText('')

            self.thread.start()













if __name__ == '__main__':
    main()

