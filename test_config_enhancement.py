#!/usr/bin/env python3
"""
测试配置文件增强功能的脚本
"""

import json
import sys
import os

# 添加当前目录到 Python 路径
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# 导入我们的类（不导入 GUI 相关部分）
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
        self.value = default_value

    def write_position(self, master, position):
        # Apply limits before writing
        position = max(self.min_value, min(self.max_value, position))
        self.value = position
        # master.set_output(self.slave_index, self.channel_index, position)

    def read_position(self, master):
        # self.value = master.get_input(self.slave_index, self.channel_index)
        return self.value

    def get_display_value(self):
        return self.value * self.conversion_factor


class DexterousHandModel:
    def __init__(self):
        self.joints = []

    def add_joint(self, joint):
        self.joints.append(joint)

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


def test_config_enhancement():
    """测试配置文件增强功能"""
    print("开始测试配置文件增强功能...")
    
    # 创建手部模型
    hand_model = DexterousHandModel()
    
    # 加载示例配置
    with open("sample_config.json", "r", encoding="utf-8") as f:
        config_data = json.load(f)
    
    hand_model.load_from_config(config_data)
    
    print(f"成功加载 {len(hand_model.joints)} 个关节:")
    
    for i, joint in enumerate(hand_model.joints):
        print(f"  关节 {i+1}: {joint.name}")
        print(f"    从站索引: {joint.slave_index}")
        print(f"    通道索引: {joint.channel_index}")
        print(f"    最小值: {joint.min_value}")
        print(f"    最大值: {joint.max_value}")
        print(f"    默认值: {joint.default_value}")
        print(f"    单位: {joint.unit}")
        print(f"    转换系数: {joint.conversion_factor}")
        print(f"    当前值: {joint.value}")
        print(f"    显示值: {joint.get_display_value()} {joint.unit}")
        print()
    
    # 测试限位功能
    print("测试限位功能:")
    test_joint = hand_model.joints[0]
    print(f"测试关节: {test_joint.name}")
    print(f"限位范围: {test_joint.min_value} - {test_joint.max_value}")
    
    # 测试超出上限
    test_joint.write_position(None, 200)
    print(f"设置值 200，实际值: {test_joint.value} (应该被限制在 {test_joint.max_value})")
    
    # 测试超出下限
    test_joint.write_position(None, -10)
    print(f"设置值 -10，实际值: {test_joint.value} (应该被限制在 {test_joint.min_value})")
    
    # 测试正常值
    test_joint.write_position(None, 90)
    print(f"设置值 90，实际值: {test_joint.value}")
    print(f"显示值: {test_joint.get_display_value()} {test_joint.unit}")
    
    print("配置文件增强功能测试完成！")


if __name__ == "__main__":
    test_config_enhancement()

