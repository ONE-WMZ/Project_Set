import requests
from functools import lru_cache
from flask import Flask
import os
from extensions import db, socketio  # 从 extensions 导入
import math

app = Flask(__name__, template_folder='../templates')
app.config['SQLALCHEMY_DATABASE_URI'] = ''                            # 数据库地址
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY') or 'default-fallback-key'  # 用于flash消息

# 高德地图API配置
# 在Flask配置中添加两个不同的密钥
app.config['AMAP_WEB_API_KEY'] = ''  # 用于后端逆地理编码     # 高德API（后端）
app.config['AMAP_JS_API_KEY'] = ''    # 用于前端地图显示      # 高德API（前端）

# 初始化扩展
db.init_app(app)
socketio.init_app(app)

# 逆地理编码服务
@lru_cache(maxsize=128)  # 添加缓存，避免重复查询相同坐标
def reverse_geocode(longitude, latitude):
    """使用高德地图Web服务API进行逆地理编码"""
    params = {
        'key': app.config['AMAP_WEB_API_KEY'],  # 使用Web服务API密钥
        'location': f"{longitude},{latitude}",
        'output': 'json'
    }
    try:
        response = requests.get('https://restapi.amap.com/v3/geocode/regeo',
                                params=params,
                                timeout=5)
        data = response.json()
        if data.get('status') == '1':
            return data['regeocode']['formatted_address']
        else:
            app.logger.error(f"逆地理编码失败: {data.get('info', '未知错误')} - {data.get('infocode', '')}")
            return None
    except Exception as e:
        app.logger.error(f"逆地理编码请求异常: {str(e)}")
        return None


# 将NMEA183格式的经纬度直接转换为高德地图(GCJ-02)使用的经纬度
def nmea_to_gcj02(nmea_lat, nmea_lon, lat_dir, lon_dir):
    """
    将 NMEA 格式的经纬度转换为 GCJ-02（高德地图使用的坐标系）

    Args:
        nmea_lat (str): 纬度，如 "3150.7848"（DDMM.MMMM）
        nmea_lon (str): 经度，如 "11711.6769"（DDDMM.MMMM）
        lat_dir (str): 'N' 或 'S'
        lon_dir (str): 'E' 或 'W'

    Returns:
        dict: {'lat': gcj_lat, 'lng': gcj_lng}
    """

    def nmea_to_decimal(coord, direction):
        """将 NMEA 格式转换为十进制度"""
        dot_index = coord.index('.')
        degrees = float(coord[:dot_index - 2])
        minutes = float(coord[dot_index - 2:])
        decimal = degrees + minutes / 60.0
        return -decimal if direction in ('S', 'W') else decimal

    def transform_lat(x, y):
        ret = -100.0 + 2.0 * x + 3.0 * y + 0.2 * y * y + 0.1 * x * y + 0.2 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(y * math.pi) + 40.0 * math.sin(y / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (160.0 * math.sin(y / 12.0 * math.pi) + 320.0 * math.sin(y / 30.0 * math.pi)) * 2.0 / 3.0
        return ret

    def transform_lng(x, y):
        ret = 300.0 + x + 2.0 * y + 0.1 * x * x + 0.1 * x * y + 0.1 * math.sqrt(abs(x))
        ret += (20.0 * math.sin(6.0 * x * math.pi) + 20.0 * math.sin(2.0 * x * math.pi)) * 2.0 / 3.0
        ret += (20.0 * math.sin(x * math.pi) + 40.0 * math.sin(x / 3.0 * math.pi)) * 2.0 / 3.0
        ret += (150.0 * math.sin(x / 12.0 * math.pi) + 300.0 * math.sin(x / 30.0 * math.pi)) * 2.0 / 3.0
        return ret

    def out_of_china(lng, lat):
        """判断是否在中国大陆境外"""
        return not (72.0 <= lng <= 137.8347 and 0.8293 <= lat <= 55.8271)

    def wgs_to_gcj(wgs_lng, wgs_lat):
        if out_of_china(wgs_lng, wgs_lat):
            return {"lat": wgs_lat, "lng": wgs_lng}

        dlat = transform_lat(wgs_lng - 105.0, wgs_lat - 35.0)
        dlng = transform_lng(wgs_lng - 105.0, wgs_lat - 35.0)

        a = 6378245.0  # 地球长半轴
        ee = 0.00669342162296594323  # 扁率

        rad_lat = wgs_lat / 180.0 * math.pi
        magic = math.sin(rad_lat)
        magic = 1 - ee * magic * magic
        sqrt_magic = math.sqrt(magic)

        dlat = (dlat * 180.0) / ((a * (1 - ee)) / (magic * sqrt_magic) * math.pi)
        dlng = (dlng * 180.0) / (a / sqrt_magic * math.cos(rad_lat) * math.pi)

        gcj_lat = wgs_lat + dlat
        gcj_lng = wgs_lng + dlng

        return {"lat": gcj_lat, "lng": gcj_lng}

    # 主流程
    wgs_lat = nmea_to_decimal(nmea_lat, lat_dir)
    wgs_lng = nmea_to_decimal(nmea_lon, lon_dir)

    result = wgs_to_gcj(wgs_lng, wgs_lat)
    return result





from routes import user_route



