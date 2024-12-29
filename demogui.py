import sys
import os
from PyQt5.QtWidgets import QApplication, QWidget, QVBoxLayout, QLabel, QPushButton, QFileDialog, QComboBox, QLineEdit, QSpinBox, QCheckBox, QMessageBox, QProgressBar
from subprocess import Popen
from PyQt5.QtCore import QThread, pyqtSignal
import subprocess


class MotionModelApp(QWidget):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("First Order Model GUI")
        self.setGeometry(100, 100, 500, 400)

        # Layout
        layout = QVBoxLayout()

        # Input Source Image
        self.source_label = QLabel("Source Image:")
        layout.addWidget(self.source_label)
        self.source_btn = QPushButton("Select Source Image")
        self.source_btn.clicked.connect(self.select_source_image)
        layout.addWidget(self.source_btn)

        # Input Driving Video
        self.driving_label = QLabel("Driving Video:")
        layout.addWidget(self.driving_label)
        self.driving_btn = QPushButton("Select Driving Video")
        self.driving_btn.clicked.connect(self.select_driving_video)
        layout.addWidget(self.driving_btn)

        # Select CRF Value
        self.crf_label = QLabel("CRF Value (Quality):")
        layout.addWidget(self.crf_label)
        self.crf_spinbox = QSpinBox()
        self.crf_spinbox.setRange(0, 51)  # FFmpeg CRF range
        self.crf_spinbox.setValue(18)
        layout.addWidget(self.crf_spinbox)

        # Model Selection (vox-256 or vox-adv-256)
        self.model_label = QLabel("Select Model:")
        layout.addWidget(self.model_label)
        self.model_dropdown = QComboBox()
        self.model_dropdown.addItems(["vox-256", "vox-adv-256"])
        layout.addWidget(self.model_dropdown)

        # Relative Flag Checkbox
        self.relative_checkbox = QCheckBox("Use --relative flag")
        layout.addWidget(self.relative_checkbox)

        # Output File Name
        self.output_label = QLabel("Output File Name:")
        layout.addWidget(self.output_label)
        self.output_name = QLineEdit()
        self.output_name.setPlaceholderText("output.mp4")
        layout.addWidget(self.output_name)

        # Progress Bar for Loading
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 100)
        layout.addWidget(self.progress_bar)

        # Process Button
        self.process_btn = QPushButton("Process Video")
        self.process_btn.clicked.connect(self.process_video)
        layout.addWidget(self.process_btn)

        # Finalize Layout
        self.setLayout(layout)

    def select_source_image(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select Source Image", "", "Images (*.png *.jpg *.jpeg)")
        if fname:
            self.source_label.setText(f"Source Image: {fname}")
            self.source_image = fname

    def select_driving_video(self):
        fname, _ = QFileDialog.getOpenFileName(self, "Select Driving Video", "", "Videos (*.mp4 *.mov)")
        if fname:
            self.driving_label.setText(f"Driving Video: {fname}")
            self.driving_video = fname

    def process_video(self):
        try:
            # Get input values
            source_image = getattr(self, 'source_image', None)
            driving_video = getattr(self, 'driving_video', None)
            crf = self.crf_spinbox.value()
            model = self.model_dropdown.currentText()
            relative_flag = '--relative' if self.relative_checkbox.isChecked() else ''
            output_file = self.output_name.text() or "output.mp4"

            # Check for missing inputs
            if not source_image or not driving_video:
                QMessageBox.critical(self, "Error", "Please select both source image and driving video.")
                return

            # Step 1: Get crop suggestions
            crop_command = f"python crop-video.py --inp \"{driving_video}\" --cpu"
            process = subprocess.run(crop_command, shell=True, capture_output=True, text=True)

            if process.returncode != 0:
                QMessageBox.critical(self, "Error", "Failed to get cropped suggestions.\n" + process.stderr)
                return

            # Extract crop details from output
            crop_output = process.stdout.splitlines()
            if not crop_output:
                QMessageBox.critical(self, "Error", "No crop suggestions received.")
                return

            # Parse crop details
            crop_ffmpeg_cmd = crop_output[0]  # Assuming first line is the FFmpeg command
            parts = crop_ffmpeg_cmd.split()
            ss = parts[parts.index('-ss') + 1]
            t = parts[parts.index('-t') + 1]
            crop_filter = crop_ffmpeg_cmd.split('-filter:v')[-1].split('"')[1]

            # Step 2: Crop video using suggested values
            cropped_video = f"{os.path.splitext(driving_video)[0]}_cropped.mp4"
            crop_apply_command = f"ffmpeg -i \"{driving_video}\" -ss {ss} -t {t} -filter:v \"{crop_filter}\" -c:v libx264 -crf {crf} -preset slow -pix_fmt yuv420p \"{cropped_video}\""
            self.progress_bar.setValue(30)
            self.run_command(crop_apply_command)

            # Step 3: Run the model
            config_file = f"config/{model}.yaml"
            checkpoint = "checkpoints/vox-cpk.pth.tar"
            demo_command = f"python demo.py --config \"{config_file}\" --driving_video \"{cropped_video}\" --source_image \"{source_image}\" --checkpoint \"{checkpoint}\" {relative_flag} --adapt_scale --cpu --result_video \"{output_file}\""
            self.progress_bar.setValue(60)
            self.run_command(demo_command)

            # Step 4: Notify Success
            self.progress_bar.setValue(100)
            QMessageBox.information(self, "Success", f"Video saved as {output_file}")

        except Exception as e:
            QMessageBox.critical(self, "Error", f"An error occurred: {str(e)}")
        
    def parse_crop_command(self, command):
        try:
            parts = command.split(" ")
            crop_params = {k: v for k, v in zip(['ss', 't', 'crop'], [parts[4], parts[6], parts[9].split('=')[1]])}
            return crop_params
        except Exception:
            return None

    def run_command(self, command):
        process = Popen(command, shell=True)
        process.wait()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = MotionModelApp()
    window.show()
    sys.exit(app.exec_())
