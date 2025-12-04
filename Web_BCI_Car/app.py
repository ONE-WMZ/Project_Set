from flask import Flask, render_template, request, jsonify
import requests
import logging

# === 配置 ===
ESP32_IP = "192.168.31.220"                    # ESP32 IP
ESP32_URL = f"http://{ESP32_IP}/cmd"

app = Flask(__name__)
app.logger.setLevel(logging.INFO)

@app.route('/')
def index():
    return render_template('index.html', esp32_ip=ESP32_IP)

@app.route('/control', methods=['POST'])
def control():
    data = request.get_json()
    action = data.get('action')

    valid_actions = {'forward', 'backward', 'left', 'right', 'stop'}
    if action not in valid_actions:
        return jsonify({'error': 'Invalid action'}), 400

    try:
        # 转发指令给 ESP32
        resp = requests.post(ESP32_URL, json={'action': action}, timeout=3)
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
        data = request.get_json(force=True)  # 即使没有 Content-Type 也尝试解析
        print("✅ 收到小车就绪通知:", data)
        return {"status": "acknowledged"}, 200
    except Exception as e:
        print("❌ 解析通知失败:", e)
        return {"error": "invalid json"}, 400

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=True)