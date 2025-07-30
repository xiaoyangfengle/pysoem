import sys
import threading
import pysoem
import xml.etree.ElementTree as ET
import argparse
import json
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget,
    QSlider, QMessageBox, QComboBox, QHBoxLayout, QGroupBox, QGridLayout,
    QFileDialog, QGraphicsScene, QGraphicsView, QGraphicsEllipseItem, QSplitter
)
from PySide6.QtCore import QTimer, Qt, QRectF
from PySide6.QtGui import QBrush, QColor
# from PySide6.QtOpenGLWidgets import QOpenGLWidget # Commented out for headless environment
# from OpenGL.GL import *
# from OpenGL.GLU import *
# from OpenGL.GLUT import glutInit, glutSolidCube # Commented out for headless environment

import matplotlib
matplotlib.use("QtAgg") # Use "QtAgg" backend for PySide6
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
from matplotlib.figure import Figure


class EtherCATJoint:
    def __init__(self, slave_index, channel_index, name="Joint", min_value=0, max_value=255, default_value=0, unit="raw", conversion_factor=1.0):
        self.slave_index = slave_index
        self.channel_index = channel_index
        self.name = name
        self.min_value = min_value
        self.max_value = max_value
        self.default_value = default_value
        self.unit = unit
        self.conversion_factor = conversion_factor
        self.value = default_value # Initialize with default value

    def write_position(self, master, position):
        # Apply limits before writing
        position = max(self.min_value, min(self.max_value, position))
        self.value = position
        master.set_output(self.slave_index, self.channel_index, position)

    def read_position(self, master):
        self.value = master.get_input(self.slave_index, self.channel_index)
        return self.value

    def get_display_value(self):
        return self.value * self.conversion_factor


class DexterousHandModel:
    def __init__(self):
        self.joints = []

    def add_joint(self, joint):
        self.joints.append(joint)

    def update_from_master(self, master):
        for joint in self.joints:
            joint.read_position(master)

    def write_to_master(self, master):
        for joint in self.joints:
            joint.write_position(master, joint.value)

    def load_from_config(self, config_data):
        self.joints.clear()
        for entry in config_data.get("joints", []):
            joint = EtherCATJoint(
                slave_index=entry["slave_index"],
                channel_index=entry["channel_index"],
                name=entry.get("name", "Joint"),
                min_value=entry.get("min_value", 0),
                max_value=entry.get("max_value", 255),
                default_value=entry.get("default_value", 0),
                unit=entry.get("unit", "raw"),
                conversion_factor=entry.get("conversion_factor", 1.0)
            )
            self.add_joint(joint)


class EtherCATMaster:
    def __init__(self, simulation_mode=False):
        self.simulation_mode = simulation_mode
        if not simulation_mode:
            self.master = pysoem.Master()
        else:
            self.master = None
        self.adapter_name = None
        self.running = False
        self.thread = None
        self.simulated_inputs = {}
        self.simulated_outputs = {}

    def find_adapters(self):
        if self.simulation_mode:
            return [type("Adapter", (), {"name": "sim", "desc": "Simulated Adapter"})()]
        return pysoem.find_adapters()

    def start(self, adapter_name):
        if self.simulation_mode:
            self.adapter_name = adapter_name
            self.running = True
            return

        self.adapter_name = adapter_name
        self.master.open(adapter_name)
        if self.master.config_init() <= 0:
            raise RuntimeError("No EtherCAT slaves found")
        self.master.config_map()
        self.master.state_check(pysoem.OP_STATE, 50000)
        self.running = True
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _run(self):
        while self.running:
            self.master.send_processdata()
            self.master.receive_processdata(2000)

    def stop(self):
        self.running = False
        if not self.simulation_mode and self.thread:
            self.thread.join()
            self.master.close()

    def set_output(self, slave_idx, byte_offset, value):
        if self.simulation_mode:
            self.simulated_outputs[(slave_idx, byte_offset)] = value
            return
        if 0 <= slave_idx < len(self.master.slaves):
            self.master.slaves[slave_idx].output[byte_offset] = value

    def get_input(self, slave_idx, byte_offset):
        if self.simulation_mode:
            return self.simulated_outputs.get((slave_idx, byte_offset), 0)
        if 0 <= slave_idx < len(self.master.slaves):
            return self.master.slaves[slave_idx].input[byte_offset]
        return 0

    @property
    def slaves(self):
        if self.simulation_mode:
            return [type("Slave", (), {"name": "SimSlave", "input": [0]*8, "output": [0]*8})() for _ in range(2)]
        return self.master.slaves


# class Hand3DWidget(QOpenGLWidget):
#     def __init__(self):
#         super().__init__()
#         self.joint_angles = [0.0 for _ in range(20)]

#     def initializeGL(self):
#         glEnable(GL_DEPTH_TEST)
#         glClearColor(0.2, 0.2, 0.2, 1.0)

#     def resizeGL(self, w, h):
#         glViewport(0, 0, w, h)
#         glMatrixMode(GL_PROJECTION)
#         glLoadIdentity()
#         gluPerspective(45.0, w / h if h != 0 else 1, 0.1, 100.0)
#         glMatrixMode(GL_MODELVIEW)

#     def paintGL(self):
#         glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
#         glLoadIdentity()
#         gluLookAt(0, 0, 30, 0, 0, 0, 0, 1, 0)

#         for i, angle in enumerate(self.joint_angles):
#             glPushMatrix()
#             glTranslatef(-10 + i * 1.2, 0, 0)
#             glRotatef(angle, 1, 0, 0)
#             glColor3f(0.5, 0.8, 1.0)
#             self.draw_finger()
#             glPopMatrix()

#     def draw_finger(self):
#         glBegin(GL_QUADS)
#         glVertex3f(-0.5, 0, -0.5)
#         glVertex3f(0.5, 0, -0.5)
#         glVertex3f(0.5, 4, -0.5)
#         glVertex3f(-0.5, 4, -0.5)

#         glVertex3f(-0.5, 0, 0.5)
#         glVertex3f(0.5, 0, 0.5)
#         glVertex3f(0.5, 4, 0.5)
#         glVertex3f(-0.5, 4, 0.5)
#         glEnd()

#     def set_joint_angle(self, finger_idx, angle):
#         if 0 <= finger_idx < len(self.joint_angles):
#             self.joint_angles[finger_idx] = angle
#             self.update()


class PlotCanvas(FigureCanvas):
    def __init__(self, parent=None, width=5, height=4, dpi=100):
        fig = Figure(figsize=(width, height), dpi=dpi)
        self.axes = fig.add_subplot(111)
        super().__init__(fig)
        self.setParent(parent)
        self.data_points = []
        self.max_points = 100 # Display last 100 points

    def update_plot(self, new_value):
        self.data_points.append(new_value)
        if len(self.data_points) > self.max_points:
            self.data_points = self.data_points[-self.max_points:]

        self.axes.cla() # Clear the current axes
        self.axes.plot(self.data_points, "b-")
        self.axes.set_title("Real-time Joint Value")
        self.axes.set_xlabel("Time Steps")
        self.axes.set_ylabel("Value")
        self.draw()


class MainWindow(QMainWindow):
    def __init__(self, ethercat_master):
        super().__init__()
        self.setWindowTitle("EtherCAT 灵巧手 Demo")
        self.master = ethercat_master
        self.hand_model = DexterousHandModel()

        self.adapter_selector = QComboBox()
        self.connect_btn = QPushButton("连接 EtherCAT 从机")
        self.connect_btn.clicked.connect(self.connect_to_slave)

        self.load_esi_btn = QPushButton("加载 ESI 配置")
        self.load_esi_btn.clicked.connect(self.load_esi_config)

        self.sliders = []
        self.output_labels = []
        self.input_labels = []
        self.plot_canvases = [] # To store plot canvases for each joint

        adapter_layout = QHBoxLayout()
        adapter_layout.addWidget(QLabel("选择适配器:"))
        adapter_layout.addWidget(self.adapter_selector)
        adapter_layout.addWidget(self.connect_btn)
        adapter_layout.addWidget(self.load_esi_btn)

        self.slave_controls = QGroupBox("从机控制")
        self.slave_layout = QGridLayout()
        self.slave_controls.setLayout(self.slave_layout)

        # self.opengl_widget = Hand3DWidget() # Commented out for headless environment

        splitter = QSplitter(Qt.Vertical)
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.addLayout(adapter_layout)
        top_layout.addWidget(self.slave_controls)

        splitter.addWidget(top_widget)
        # splitter.addWidget(self.opengl_widget) # Commented out for headless environment
        splitter.setStretchFactor(1, 1)

        self.setCentralWidget(splitter)

        self.timer = QTimer()
        self.timer.timeout.connect(self.update_inputs)

        self.populate_adapters()

    def populate_adapters(self):
        adapters = self.master.find_adapters()
        for adapter in adapters:
            self.adapter_selector.addItem(f"{adapter.name} ({adapter.desc})", adapter.name)

    def connect_to_slave(self):
        adapter_name = self.adapter_selector.currentData()
        if not adapter_name:
            QMessageBox.critical(self, "错误", "请选择一个适配器")
            return
        try:
            self.master.start(adapter_name)
            self.connect_btn.setEnabled(False)
            self.adapter_selector.setEnabled(False)
            self.create_slave_controls()
            self.timer.start(100)
            QMessageBox.information(self, "成功", f"已连接到适配器: {adapter_name}")
        except Exception as e:
            QMessageBox.critical(self, "连接失败", str(e))

    def load_esi_config(self):
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 ESI 或 JSON 配置文件", "", "Config Files (*.xml *.json)")
        if not file_path:
            return

        try:
            if file_path.endswith(".json"):
                with open(file_path, "r", encoding="utf-8") as f:
                    config_data = json.load(f)
                    self.hand_model.load_from_config(config_data)
                    QMessageBox.information(self, "配置成功", "已从 JSON 配置加载关节")
            else:
                tree = ET.parse(file_path)
                root = tree.getroot()

                joints = []
                for i, dev in enumerate(root.findall(".//Descriptions/Devices/Device")):
                    name = dev.findtext("Name", f"Joint_{i}")
                    mapping_entries = dev.findall(".//RxPdo/Entry")
                    for j, entry in enumerate(mapping_entries):
                        joint = {
                            "slave_index": i,
                            "channel_index": j,
                            "name": entry.findtext("Name", name + f"_{j}")
                        }
                        joints.append(joint)

                # 兼容查找 <Descriptions><Groups><Group><Joint> 节点结构
                if not joints:
                    for joint_elem in root.findall(".//Descriptions/Groups/Group/Joint"):
                        joint = {
                            "slave_index": int(joint_elem.attrib.get("slave_index", 0)),
                            "channel_index": int(joint_elem.attrib.get("channel_index", 0)),
                            "name": joint_elem.attrib.get("name", "Joint")
                        }
                        joints.append(joint)

                if joints:
                    config_data = {"joints": joints}
                    self.hand_model.load_from_config(config_data)
                    QMessageBox.information(self, "配置成功", f"已从 ESI 文件配置 {len(joints)} 个关节")
                else:
                    QMessageBox.warning(self, "警告", "未在 ESI 文件中找到关节映射，已跳过")

        except Exception as e:
            QMessageBox.critical(self, "加载失败", str(e))

    def create_slave_controls(self):
        # Clear existing controls
        for i in reversed(range(self.slave_layout.count())):
            widget = self.slave_layout.itemAt(i).widget()
            if widget:
                widget.setParent(None)
        self.sliders.clear()
        self.output_labels.clear()
        self.input_labels.clear()
        self.plot_canvases.clear()

        for idx, joint in enumerate(self.hand_model.joints):
            slider = QSlider(Qt.Horizontal)
            slider.setRange(joint.min_value, joint.max_value)
            slider.setValue(joint.default_value)
            slider.setEnabled(True)
            slider.valueChanged.connect(lambda val, joint=joint, idx=idx: self.on_slider_change(joint, val, idx))

            output_label = QLabel(f"{joint.name} 输出值: {joint.default_value} {joint.unit}")
            input_label = QLabel(f"{joint.name} 输入值: {joint.default_value} {joint.unit}")

            # plot_canvas = PlotCanvas(self, width=2, height=1, dpi=50) # Smaller plot for each joint
            # self.plot_canvases.append((joint, plot_canvas))

            self.slave_layout.addWidget(QLabel(f"{joint.name}"), idx, 0)
            self.slave_layout.addWidget(slider, idx, 1)
            self.slave_layout.addWidget(output_label, idx, 2)
            self.slave_layout.addWidget(input_label, idx, 3)
            # self.slave_layout.addWidget(plot_canvas, idx, 4) # Add plot canvas

            self.sliders.append((joint, slider))
            self.output_labels.append((joint, output_label))
            self.input_labels.append((joint, input_label))

    def on_slider_change(self, joint, value, idx):
        for (j, label) in self.output_labels:
            if j == joint:
                label.setText(f"{joint.name} 输出值: {joint.get_display_value()} {joint.unit}")
        joint.write_position(self.master, value)
        # self.opengl_widget.set_joint_angle(idx, value / 255 * 90) # Commented out for headless environment

    def update_inputs(self):
        for (joint, label) in self.input_labels:
            value = joint.read_position(self.master)
            label.setText(f"{joint.name} 输入值: {joint.get_display_value()} {joint.unit}")

        # for (joint, plot_canvas) in self.plot_canvases:
        #     value = joint.value # Use the value already read in the loop above
        #     plot_canvas.update_plot(value)


def main():
    parser = argparse.ArgumentParser(description="EtherCAT GUI for Dexterous Hand")
    parser.add_argument("--simulate", action="store_true", help="Run in simulation mode without real EtherCAT devices")
    parser.add_argument("--adapter", type=str, help="Specify adapter name to auto-connect")
    args = parser.parse_args()

    # glutInit() # Commented out for headless environment

    master = EtherCATMaster(simulation_mode=args.simulate)
    app = QApplication(sys.argv)
    window = MainWindow(master)
    window.show()

    if args.adapter:
        try:
            master.start(args.adapter)
            window.connect_btn.setEnabled(False)
            window.adapter_selector.setEnabled(False)
            window.create_slave_controls()
            window.timer.start(100)
        except Exception as e:
            QMessageBox.critical(window, "连接失败", str(e))

    exit_code = app.exec()
    master.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()


