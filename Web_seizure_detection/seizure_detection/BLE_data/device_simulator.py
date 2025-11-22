import random
import time
import logging
from datetime import datetime

import requests

# 配置日志记录
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def get_registered_devices():
    """
    模拟从数据库获取注册设备列表。
    返回值：设备 ID 列表（例如 ['device_001', 'device_002']）。
    """
    # 这里可以替换为实际的数据库查询逻辑
    return ['3']   # '1', '2',

def generate_device_data(device_id):
    """
    生成单个设备的模拟数据。
    参数：
        device_id (str): 设备 ID。
    返回值：包含设备数据的字典。
    """

    return {
        'device_id': device_id,
        'position_x': round(11349.73472 + random.uniform(-0.01, 0.01), 6),  # 经度微调
        'position_y': round(2236.40101 + random.uniform(-0.01, 0.01), 6),   # 纬度微调
        'user_data': [[random.random() for _ in range(512)] for _ in range(22)],
        'time_stamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

def send_data_to_server(payload):
    """
    将设备数据发送到服务器。
    参数：
        payload (dict): 设备数据。
    """
    url = "http://8.154.30.107/api/device/data"  # 替换为实际的服务器地址
    try:
        response = requests.post(url, json=payload)
        if response.status_code == 200:
            logging.info(f"[发送成功] 设备 {payload['device_id']}")
        else:
            logging.error(f"[发送失败] 设备 {payload['device_id']} -> {response.status_code} {response.text}")
    except Exception as e:
        logging.error(f"[发送失败] 设备 {payload['device_id']} -> {e}")

def simulate_device_data():
    """
    模拟设备数据上传。
    参数：
        interval (int): 数据发送间隔时间（秒）。
    """
    devices = get_registered_devices()
    if not devices:
        logging.error("错误：数据库中没有注册设备！请先添加设备。")
        return

    logging.info(f"准备模拟 {len(devices)} 台设备的数据上传...")

    try:
        while True:
            for device_id in devices:
                payload = generate_device_data(device_id)
                # print(payload)
                send_data_to_server(payload)
            time.sleep(2)
    except KeyboardInterrupt:
        logging.info("模拟程序已停止。")
    except Exception as e:
        logging.error(f"模拟程序发生错误：{e}")

if __name__ == '__main__':
    simulate_device_data()