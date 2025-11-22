import numpy as np
import torch
import os
import torch.nn as nn
import torch.nn.functional as F
import time  # 引入时间模块

""" 数据格式调整（解包）"""
def data_trans(data):
    data = np.array(data)
    if data.shape != (20, 120):
        raise ValueError(f"Expected input shape (20, 120), but got {data.shape}")
    packet_2d_list = [row.reshape(20, 6) for row in data]
    restored_segment_transposed = np.vstack(packet_2d_list)  # (400, 6)
    restored_segment = restored_segment_transposed.T  # (6, 400)

    # 转换为 torch.Tensor，并增加 batch 维度
    tensor_data = torch.from_numpy(restored_segment).float().unsqueeze(0)  # shape: (1, 6, 400)

    # print(tensor_data.shape)
    return tensor_data


""" 多尺度+注意力"""
"""model_seizure（Test Accuracy: 0.9219）"""
class LightweightMultiScaleConv(nn.Module):
    """修正后的轻量级多尺度卷积模块"""

    def __init__(self, in_channels, out_channels):
        super().__init__()
        # 确保out_channels能被3整除
        assert out_channels % 3 == 0, "out_channels must be divisible by 3"

        self.conv3 = nn.Conv1d(in_channels, out_channels // 3, kernel_size=3, padding=1)
        self.conv5 = nn.Conv1d(in_channels, out_channels // 3, kernel_size=5, padding=2)
        self.conv7 = nn.Conv1d(in_channels, out_channels // 3, kernel_size=7, padding=3)

        # 高效注意力机制
        self.attention = nn.Sequential(
            nn.AdaptiveAvgPool1d(1),
            nn.Flatten(),
            nn.Linear(out_channels, out_channels // 4),
            nn.ReLU(),
            nn.Linear(out_channels // 4, 3),  # 注意这里的输出是3，对应三个分支
            nn.Softmax(dim=1)
        )

        self.bn = nn.BatchNorm1d(out_channels)
        self.act = nn.Mish()  # Mish 激活函数

    def forward(self, x):
        # 多尺度特征提取
        x1 = self.conv3(x)
        x2 = self.conv5(x)
        x3 = self.conv7(x)

        # 拼接特征 -> [B, 63, L]
        out = torch.cat([x1, x2, x3], dim=1)

        # 计算注意力权重 -> [B, 3]
        weights = self.attention(out)

        # 将输出切分为三部分 -> 每个 [B, 21, L]
        branch_channels = out.shape[1] // 3
        x1_, x2_, x3_ = torch.split(out, split_size_or_sections=branch_channels, dim=1)

        # 加权融合
        weighted = torch.cat([
            x1_ * weights[:, 0].view(-1, 1, 1),
            x2_ * weights[:, 1].view(-1, 1, 1),
            x3_ * weights[:, 2].view(-1, 1, 1)
        ], dim=1)

        return self.act(self.bn(weighted))


class EEGLightNet(nn.Module):
    """修正后的6通道专用轻量网络"""

    def __init__(self, input_shape=(6, 400), num_classes=2):
        super().__init__()

        # 输入处理层
        self.input_block = nn.Sequential(
            nn.Conv1d(6, 16, kernel_size=1),  # 通道混合
            nn.BatchNorm1d(16),
            nn.ReLU()
        )

        # 多尺度特征提取（确保输出通道数是3的倍数）
        self.feature_extractor = nn.Sequential(
            LightweightMultiScaleConv(16, 63),  # 63=3×21
            nn.MaxPool1d(2),
            nn.Dropout1d(0.5),
            LightweightMultiScaleConv(63, 126),  # 126=3×42
            nn.MaxPool1d(2),
            nn.Dropout1d(0.5),
            LightweightMultiScaleConv(126, 252),  # 252=3×84
            nn.AdaptiveAvgPool1d(1)
        )

        # 分类头
        self.classifier = nn.Sequential(
            nn.Flatten(),
            nn.Linear(252, 64),
            nn.Dropout(0.6),
            nn.Mish(),
            nn.Linear(64, num_classes)
        )

    def forward(self, x):
        x = self.input_block(x)
        x = self.feature_extractor(x)
        return self.classifier(x)



""" 加载模型 """
model = EEGLightNet()
# 获取当前文件所在目录（即 models 目录）
current_dir = os.path.dirname(os.path.abspath(__file__))
model_path = os.path.join(current_dir, 'model_seizure.pth')
model.load_state_dict(torch.load(model_path, map_location='cpu'))
model.eval()


""" 检测函数 """
def model_class(user_data):

    model.eval()
    data = data_trans(user_data)  # 返回 torch.Tensor
    # 开始计时
    # start_time = time.time()
    with torch.no_grad():
        output = model(data)       # 癫痫检测
        # 获取概率和类别
        _, predicted = torch.max(output, 1)
        predicted_class = predicted.item()
        print('[检测成功]')
    # 结束计时
    # end_time = time.time()
    # 计算推理耗时并打印
    # inference_time = end_time - start_time

    return predicted_class    # inference_time


# 测试数据
# np.random.seed(0)
# all_time = []
# for i in range(300):
#     data_x = np.random.rand(20, 120)
#     detect, a_time = model_class(data_x)
#     all_time.append(a_time*1000)
#     # print(detect)
# print(all_time)
