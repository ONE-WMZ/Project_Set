import asyncio
import time
from bleak import BleakScanner, BleakClient
import numpy as np
import random

import matplotlib.pyplot as plt

# 配置参数
TARGET_NAME = "Seizure-3"
WRITE_UUID = "6E400002-B5A3-F393-E0A9-E50E24DCCA9E"

# 数据包配置
TOTAL_FLOATS = 6 * 400        # 总共发送 2400 个浮点数 <（22*400=8800）
FLOATS_PER_PACKET = 6*20        # 每包 120个 float (120*4=480 bytes) < 512/4=128
PACKETS_PER_BATCH = 20        # 分为 2400/120=20 个包
BYTES_PER_FLOAT = 4

all_send_time = []

def generate_batch(npy_file='BLE_data.npy'):
    """
    从 shape=(6, 80000) 的 .npy 文件中随机截取一个 (6, 400) 的子片段，
    并按照 FLOATS_PER_PACKET 分成多个 packet。
    返回值：列表，每个元素是一个长度为 120 的 list，共 20 个 packets。
    """
    data = np.load(npy_file)  # 加载整个数据
    # 随机选择起始位置（确保不会越界）
    start_idx = random.randint(0, data.shape[1] - 400)
    segment = data[:, start_idx:start_idx + 400]  # 截取 (6, 400)
    # 转置为 (400, 6)
    segment_transposed = segment.T  # shape: (400, 6)
    # 将每 20 个时间步打包为一个 packet (20 × 6 = 120 floats)
    packets = []
    for i in range(0, 400, 20):
        packet_data = segment_transposed[i:i+20]  # shape: (20, 6)
        packet_flat = packet_data.flatten()       # shape: (120,)
        packets.append(packet_flat.tolist())      # 转换为 Python list[float]
    return packets

# def generate_batch():
#     """生成一个完整的批次数据"""
#     random_floats = np.random.rand(TOTAL_FLOATS).astype(np.float32)
#     return [random_floats[i*FLOATS_PER_PACKET:(i+1)*FLOATS_PER_PACKET] for i in range(PACKETS_PER_BATCH)]

async def scan_devices():
    """扫描BLE设备"""
    print(f"正在扫描名称为 '{TARGET_NAME}' 的设备...")
    devices = await BleakScanner.discover(timeout=5)
    for d in devices:
        if d.name and TARGET_NAME.lower() in d.name.lower():
            print(f"找到目标设备: {d}")
            return d.address
    print("未找到匹配的设备")
    return None

async def send_batches_continuously(client):
    """
    持续发送完整批次的数据
    每批 2400 个 float，分为 20 个包，每包 120 字节
    控制每 2 秒发送一个批次
    """
    batch_interval = 1.0  # 每 2 秒发送一个批次
    batches_sent = 0
    timestamps = []

    print(f"\n🔄 开始持续发送完整批次数据（每批 {TOTAL_FLOATS} 个 float，{PACKETS_PER_BATCH} 包，每包 {FLOATS_PER_PACKET} 个 float）...\n")

    try:
        while True:
            start_batch_time = time.perf_counter()
            batch = generate_batch()
            batches_sent += 1

            for i, packet_floats in enumerate(batch):
                packet_array = np.array(packet_floats, dtype=np.float32)
                packet_bytes = packet_array.tobytes()

                start_time = time.perf_counter()
                await client.write_gatt_char(WRITE_UUID, packet_bytes)
                end_time = time.perf_counter()

                print(
                    f"✅ 已发送第 {batches_sent}-{i + 1} 个数据包，大小: {len(packet_bytes)} 字节，耗时 {(end_time - start_time) * 1000:.2f} ms")
            end_batch_time = time.perf_counter()
            timestamps.append(end_batch_time)

            print(f"📦 第 {batches_sent} 批数据已发送完成，耗时 {(end_batch_time - start_batch_time)*1000:.2f} ms")

            all_send_time.append((end_batch_time - start_batch_time))
            # 控制批次间隔为 2 秒
            remaining_time = batch_interval - (end_batch_time - start_batch_time)
            if remaining_time > 0:
                await asyncio.sleep(remaining_time)

    except asyncio.CancelledError:
        print("\n🛑 用户中断发送过程")
        print(all_send_time)
    except Exception as e:
        print(f"\n❌ 发送过程中发生错误: {e}")

    # 输出统计信息
    if len(timestamps) >= 2:
        total_time = timestamps[-1] - timestamps[0]
        rate = batches_sent / total_time
        print(f"\n📊 总共发送 {batches_sent} 个批次，总耗时：{total_time:.4f} 秒")
        print(f"📊 平均发送频率：{rate:.2f} 批次/秒")
    else:
        print("\n⚠️ 没有成功发送任何批次数据")

async def main():
    device_address = await scan_devices()
    if not device_address:
        return

    client = BleakClient(device_address)

    print(f"尝试连接到 {device_address}...")

    try:
        await client.connect(timeout=10.0)
        print(f"✅ 成功连接到 {client.address}")
    except Exception as e:
        print(f"❌ 连接失败: {e}")
        return

    if not client.is_connected:
        print("❌ 客户端未连接")
        return

    print("开始持续发送完整批次数据...")
    sender_task = asyncio.create_task(send_batches_continuously(client))

    try:
        await sender_task
    except KeyboardInterrupt:
        print("\n👋 正在等待任务安全结束...")
        sender_task.cancel()
        await asyncio.gather(sender_task, return_exceptions=True)

    await client.disconnect()
    print("🔌 已断开连接")

if __name__ == "__main__":
    asyncio.run(main())