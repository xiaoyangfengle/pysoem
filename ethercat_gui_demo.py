import sys
import threading
import pysoem
import xml.etree.ElementTree as ET
from PySide6.QtWidgets import (
    QApplication, QMainWindow, QPushButton, QLabel, QVBoxLayout, QWidget,
    QSlider, QMessageBox, QComboBox, QHBoxLayout, QGroupBox, QGridLayout,
    QFileDialog, QGraphicsScene, QGraphicsView, QGraphicsEllipseItem, QSplitter
)
from PySide6.QtCore import QTimer, Qt, QRectF
from PySide6.QtGui import QBrush, QColor
from PySide6.QtOpenGLWidgets import QOpenGLWidget
from OpenGL.GL import *
from OpenGL.GLU import *


class EtherCATJoint:
    def __init__(self, slave_index, channel_index, name="Joint"):
        self.slave_index = slave_index
        self.channel_index = channel_index
        self.name = name
        self.value = 0

    def write_position(self, master, position):
        self.value = position
        master.set_output(self.slave_index, self.channel_index, position)

    def read_position(self, master):
        self.value = master.get_input(self.slave_index, self.channel_index)
        return self.value


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
            return [type('Adapter', (), {'name': 'sim', 'desc': 'Simulated Adapter'})()]
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
            return [type('Slave', (), {'name': 'SimSlave', 'input': [0]*8, 'output': [0]*8})() for _ in range(2)]
        return self.master.slaves


class Hand3DWidget(QOpenGLWidget):
    def __init__(self):
        super().__init__()
        self.joint_angles = [0.0 for _ in range(5)]

    def initializeGL(self):
        glEnable(GL_DEPTH_TEST)
        glClearColor(0.2, 0.2, 0.2, 1.0)

    def resizeGL(self, w, h):
        glViewport(0, 0, w, h)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        gluPerspective(45.0, w / h if h != 0 else 1, 0.1, 100.0)
        glMatrixMode(GL_MODELVIEW)

    def paintGL(self):
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glLoadIdentity()
        gluLookAt(0, 0, 20, 0, 0, 0, 0, 1, 0)

        for i, angle in enumerate(self.joint_angles):
            glPushMatrix()
            glTranslatef(-8 + i * 4, 0, 0)
            glRotatef(angle, 1, 0, 0)
            glColor3f(0.5, 0.8, 1.0)
            self.draw_finger()
            glPopMatrix()

    def draw_finger(self):
        glBegin(GL_QUADS)
        glVertex3f(-0.5, 0, -0.5)
        glVertex3f(0.5, 0, -0.5)
        glVertex3f(0.5, 4, -0.5)
        glVertex3f(-0.5, 4, -0.5)

        glVertex3f(-0.5, 0, 0.5)
        glVertex3f(0.5, 0, 0.5)
        glVertex3f(0.5, 4, 0.5)
        glVertex3f(-0.5, 4, 0.5)
        glEnd()

    def set_joint_angle(self, finger_idx, angle):
        if 0 <= finger_idx < len(self.joint_angles):
            self.joint_angles[finger_idx] = angle
            self.update()


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

        adapter_layout = QHBoxLayout()
        adapter_layout.addWidget(QLabel("选择适配器:"))
        adapter_layout.addWidget(self.adapter_selector)
        adapter_layout.addWidget(self.connect_btn)
        adapter_layout.addWidget(self.load_esi_btn)

        self.slave_controls = QGroupBox("从机控制")
        self.slave_layout = QGridLayout()
        self.slave_controls.setLayout(self.slave_layout)

        self.opengl_widget = Hand3DWidget()

        splitter = QSplitter(Qt.Vertical)
        top_widget = QWidget()
        top_layout = QVBoxLayout(top_widget)
        top_layout.addLayout(adapter_layout)
        top_layout.addWidget(self.slave_controls)

        splitter.addWidget(top_widget)
        splitter.addWidget(self.opengl_widget)
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
        file_path, _ = QFileDialog.getOpenFileName(self, "选择 ESI 配置文件", "", "ESI Files (*.xml)")
        if file_path:
            try:
                tree = ET.parse(file_path)
                root = tree.getroot()
                for dev in root.findall(".//Device"):
                    vendor_id = dev.findtext("Type/Identity/VendorID")
                    product_code = dev.findtext("Type/Identity/ProductCode")
                    print(f"ESI 设备: Vendor={vendor_id}, Product={product_code}")
                QMessageBox.information(self, "ESI 加载", "ESI 配置加载成功")
            except Exception as e:
                QMessageBox.critical(self, "加载失败", str(e))

    def create_slave_controls(self):
        for i, slave in enumerate(self.master.slaves):
            for j in range(2):
                joint = EtherCATJoint(i, j, name=f"Joint_{i}_{j}")
                self.hand_model.add_joint(joint)

                slider = QSlider(Qt.Horizontal)
                slider.setRange(0, 255)
                slider.setValue(0)
                slider.setEnabled(True)
                slider.valueChanged.connect(lambda val, joint=joint: self.on_slider_change(joint, val))

                output_label = QLabel(f"{joint.name} 输出值: 0")
                input_label = QLabel(f"{joint.name} 输入值: 0")

                row = i * 2 + j
                self.slave_layout.addWidget(QLabel(f"从机 {i} 通道 {j}"), row, 0)
                self.slave_layout.addWidget(slider, row, 1)
                self.slave_layout.addWidget(output_label, row, 2)
                self.slave_layout.addWidget(input_label, row, 3)

                self.sliders.append((joint, slider))
                self.output_labels.append((joint, output_label))
                self.input_labels.append((joint, input_label))

    def on_slider_change(self, joint, value):
        for (j, label) in self.output_labels:
            if j == joint:
                label.setText(f"{joint.name} 输出值: {value}")
        joint.write_position(self.master, value)
        if joint.slave_index == 0 and joint.channel_index < 5:
            self.opengl_widget.set_joint_angle(joint.channel_index, value / 255 * 90)

    def update_inputs(self):
        for (joint, label) in self.input_labels:
            value = joint.read_position(self.master)
            label.setText(f"{joint.name} 输入值: {value}")


def main():
    simulation = '--simulate' in sys.argv
    master = EtherCATMaster(simulation_mode=simulation)
    app = QApplication(sys.argv)
    window = MainWindow(master)
    window.show()
    exit_code = app.exec()
    master.stop()
    sys.exit(exit_code)


if __name__ == "__main__":
    main()
