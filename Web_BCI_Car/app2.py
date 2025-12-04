from flask import Flask, render_template, request, jsonify
import requests
import logging

# === 配置 ===
ESP32_IP = "10.145.71.170"
ESP32_URL = f"http://{ESP32_IP}/cmd"

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

# 方向映射：MATLAB 数字 → 控制动作
DIRECTION_TO_ACTION = {
    "1": "forward",
    "2": "backward",
    "3": "left",
    "4": "right"
}

@app.route('/')
def index():
    return render_template('index.html', esp32_ip=ESP32_IP)

@app.route('/bci_direction', methods=["POST"])
def bci_direction():
    """
    接收来自 MATLAB 的方向指令：
    JSON: {"direction": 1} (1=前进, 2=后退, 3=左转, 4=右转)
    直接转发到 ESP32。
    """
    try:
        data = request.get_json(force=True)
        direction = data.get("direction")

        if direction is None:
            return jsonify({"error": "missing 'direction' field"}), 400

        direction_str = str(direction)
        action = DIRECTION_TO_ACTION.get(direction_str)
        if not action:
            app.logger.warning(f"未知方向: {direction_str}")
            return jsonify({"error": "invalid direction"}), 400

        app.logger.info(f"✅ 收到来自 MATLAB 的方向: {direction_str} → action='{action}'")

        # 直接发送到 ESP32
        try:
            resp = requests.post(ESP32_URL, json={"action": action}, timeout=2.0)
            if resp.status_code == 200:
                app.logger.info(f"已发送 '{action}' 到 ESP32")
                return jsonify({
                    "status": "ok",
                    "direction": direction_str,
                    "action": action,
                    "esp32_response": resp.json()
                }), 200
            else:
                error_msg = resp.json().get("error", "Unknown error from ESP32")
                app.logger.error(f"ESP32 返回错误: {error_msg}")
                return jsonify({
                    "status": "error",
                    "direction": direction_str,
                    "action": action,
                    "esp32_error": error_msg
                }), 500
        except requests.exceptions.RequestException as e:
            app.logger.error(f"❌ 无法连接 ESP32: {e}")
            return jsonify({"error": "ESP32 unreachable"}), 500

    except Exception as e:
        app.logger.error(f"❌ 解析请求失败: {e}")
        return jsonify({"error": "invalid request"}), 400


@app.route('/control', methods=['POST'])
def control():
    """用于网页或其它客户端直接发送控制指令"""
    data = request.get_json()
    action = data.get('action')
    valid_actions = {'forward', 'backward', 'left', 'right', 'stop'}
    if action not in valid_actions:
        return jsonify({'error': 'Invalid action'}), 400
    try:
        resp = requests.post(ESP32_URL, json={'action': action}, timeout=2)
        if resp.status_code == 200:
            app.logger.info(f"Sent '{action}' to ESP32")
            return jsonify({'status': 'OK'})
        else:
            error_msg = resp.json().get('error', 'Unknown error from ESP32')
            return jsonify({'error': error_msg}), 500
    except requests.exceptions.RequestException as e:
        app.logger.error(f"Failed to connect to ESP32: {e}")
        return jsonify({'error': 'ESP32 unreachable'}), 500


@app.route('/notify', methods=['POST'])
def notify():
    try:
        data = request.get_json(force=True)
        print("✅ 收到小车就绪通知:", data)
        return {"status": "acknowledged"}, 200
    except Exception as e:
        print("❌ 解析通知失败:", e)
        return {"error": "invalid json"}, 400


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)