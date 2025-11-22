import logging
import threading
import time
from collections import deque
from datetime import datetime
from threading import Lock, Thread
from uuid import uuid4

from flask import render_template, jsonify, request, flash, redirect, url_for, session
from flask_socketio import join_room, leave_room
from sqlalchemy.exc import IntegrityError
from werkzeug.security import generate_password_hash, check_password_hash

from models.user import User, User_history, RegistrationForm, Device
from models.seizure_class import model_class     # 分类模型
from routes import app, reverse_geocode, db, socketio, nmea_to_gcj02

from datetime import datetime
from zoneinfo import ZoneInfo
import json
# 存储设备队列的全局字典
device_queues = {}
device_locks = {}

def initialize_device_queues():
    devices = Device.query.all()
    print(f"从数据库加载的设备数量: {len(devices)}")
    for device in devices:
        device_id = str(device.Device_id)
        device_queues[device_id] = deque()
        device_locks[device_id] = Lock()
        device.status = False
        db.session.commit()
        print(f"设备 {device_id} 的队列已初始化")

@app.route('/api/device/data', methods=['POST'])
def post_data():
    data = request.json
    """
        data = {
            device_id: 3 ;
            position_x: ;   (N,E)
            position_y: ;
            user_data: ([22,512]);
            time_stamp: 2025.05.21 ;
        }
    """
    print("[接收到设备数据]")
    device_id = str(data.get('device_id'))
    # 动态初始化设备队列和锁
    if device_id not in device_queues:
        device_queues[device_id] = deque()
        device_locks[device_id] = Lock()

        # 动态启动线程
        thread = threading.Thread(target=process_device_queue, args=(device_id,))
        thread.daemon = True
        thread.start()
        print(f"[动态启动设备 {device_id} 的后台线程]")


    # 插入数据到队列
    try:
        with device_locks[device_id]:
            # NVME0813 -> 高德坐标 : nmea_to_gcj02   函数
            user_data = data['user_data']
            # 数据处理：（user_data）
            # 转换为二维数组
            # result = []
            # for item in user_data:
            #     # 去除首尾的方括号，并按空格分割
            #     numbers = item.strip('[]').split()
            #     # 将字符串转换为浮点数
            #     float_numbers = [float(num) for num in numbers]
            #     result.append(float_numbers)
            # print(user_data)
            now = datetime.now()
            user_data = model_class(user_data)        # 癫痫检测模型
            gps = nmea_to_gcj02(data['position_x'], data['position_y'], 'N', 'E')
            if gps['lat'] == 0 and gps['lng'] == 0:
                last_record = User_history.query.filter_by(Device_id=device_id) \
                    .order_by(User_history.time_stamp.desc()).first()
                gps['lat'] = last_record.position_x
                gps['lng'] = last_record.position_y

            device_queues[device_id].append({
                'device_id': device_id,                                                 # 设备ID
                'position_x': gps['lat'],                                               # 定位信息
                'position_y': gps['lng'],
                'address': reverse_geocode(gps['lat'], gps['lng']),                     # 位置-逆编码
                'user_data': user_data,                                                 # 原始数据
                # 'user_status': int(data['user_data']),                                # 模型检测后->数据
                'time_stamp': now.strftime("%Y-%m-%d %H:%M:%S")                         # 时间戳
            })
        # print(f"设备 {device_id} 的队列内容: {list(device_queues[device_id])}")
        # 返回接收状态和检测后的用户状态
        return jsonify({'message': 'Data received', 'status': str(user_data)}), 200
    except Exception as e:
        print(f"插入队列失败: {str(e)}")
        return jsonify({'error': f'Failed to process data: {str(e)}'}), 400


def process_device_queue(device_id):
    # print(f"设备 {device_id} 的后台线程已启动")
    with app.app_context():  # 手动创建应用上下文
        while True:
            if device_id in device_queues:
                queue = device_queues[device_id]
                lock = device_locks[device_id]

                if queue:
                    with lock:
                        data = queue.popleft()
                        # print(f"从队列中取出数据: {data}")

                    # # 更新设备状态为在线
                    # try:
                    #     device = Device.query.filter_by(device_id=device_id).first()
                    #     if device:
                    #         device.status = True
                    #         db.session.commit()
                    #         print(f"设备 {device_id} 状态更新为在线")
                    # except Exception as e:
                    #     print(f"更新设备状态失败: {str(e)}")

                    # 使用 WebSocket 将数据发送到设备房间
                    print(f"[发送数据到房间: device_{device_id}]->数据: {data}")
                    socketio.emit('update_data', data, room=f'device_{device_id}')

                    # 将数据存入历史数据库
                    try:
                        history_entry = User_history(
                            Device_id=data['device_id'],
                            user_data=data['user_data'],
                            position_x=data['position_x'],
                            position_y=data['position_y'],
                            time_stamp=data['time_stamp']
                        )
                        db.session.add(history_entry)
                        db.session.commit()
                        # print(f"数据已存入历史数据库: {data}")
                        print("[数据已存入历史数据库]")
                    except Exception as e:
                        print(f"存储历史数据失败: {str(e)}")
                else:
                    # print(f"设备 {device_id} 的队列为空")
                    continue
            time.sleep(1)



def start_device_threads():
    print("[开始启动设备线程]")
    for device_id in device_queues.keys():
        thread = threading.Thread(target=process_device_queue, args=(device_id,))
        thread.daemon = True
        thread.start()
        print(f"[启动设备 {device_id} 的后台线程]")

@socketio.on('connect')
def handle_connect():
    print('[客户 已连接]')

@socketio.on('disconnect')
def handle_disconnect():
    print('[客户 已断开连接]')

@socketio.on('join')
def on_join(data):
    user_ = User.query.get(session['user_id'])
    device_id_ = user_.Device_id
    device_id = data.get('device_id')
    if not device_id and device_id != device_id_:
        return {'error': 'Missing device_id'}, 400


    # 将客户端加入设备房间
    join_room(f'device_{device_id}')
    print(f'{user_.ID} joined room: device_{device_id}')
    return {'message': f'Joined room: device_{device_id}'}

@socketio.on('leave')
def on_leave(data):
    device_id = data.get('device_id')
    if not device_id:
        return {'error': 'Missing device_id'}, 400

    # 将客户端移出设备房间
    leave_room(f'device_{device_id}')
    print(f'Client left room: device_{device_id}')
    return {'message': f'Left room: device_{device_id}'}

# ------------------------------- 页面路由 -------------------------------
@app.route('/user')
def user():
    """用户主页"""
    if 'user_id' not in session:
        return redirect(url_for('login'))

    user_ = User.query.get(session['user_id'])
    if not user_ or not user_.Device_id:
        return redirect(url_for('login'))

    device_id = user_.Device_id
    last_record = User_history.query.filter_by(Device_id=device_id) \
        .order_by(User_history.time_stamp.desc()).first()

    initial_data = {
        'device_status': 0,
        'user_status': 0,
        'position_x': 0,
        'position_y': 0,
        'address': '未知位置',
        'timestamp': '--'
    }

    if last_record:
        initial_data.update({
            'device_status': 0,
            'user_status': 0,
            'position_x': last_record.position_x,
            'position_y': last_record.position_y,
            'address': reverse_geocode(last_record.position_x, last_record.position_y),
            'timestamp': last_record.time_stamp.isoformat()
        })

    return render_template('user.html',
                           user_info=user_,
                           initial_data=initial_data)

# ---------------------------------------------------------------------------------------------------------------------
@app.route('/', methods=['GET', 'POST'])
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        if 'user_id' in session:
            return redirect('/user')
        return render_template('login.html')

    account = request.form.get('account')
    password = request.form.get('password')

    user_ = User.query.filter_by(Account=account).first()
    if user_ and check_password_hash(user_.Password, password):
        session['user_id'] = user_.ID
        flash('登录成功!', 'success')
        return redirect('/user')

    flash('账号或密码错误', 'danger')
    return render_template('login.html')


@app.route('/logout')
def logout():
    try:
        user_id = session.get('user_id')
        if user_id:
            logging.info(f'用户 {user_id} 已退出登录')
        session.clear()
        flash('您已成功退出登录', 'success')
        return redirect(url_for('login'))
    except Exception as e:
        app.logger.error(f"退出登录错误: {str(e)}")
        return jsonify({'error': '内部服务器错误'}), 500


@app.route('/enroll', methods=['GET', 'POST'])
def enroll():
    if request.method == 'POST':
        form = RegistrationForm(request.form)
        if form.validate_on_submit():
            hashed_password = generate_password_hash(form.password.data)
            user_ = User(
                ID=str(uuid4()),
                Account=form.account.data,
                Password=hashed_password,
                Name=form.name.data,
                Age=form.age.data,
                Phone=form.phone.data,
                Device_id=form.device_id.data,
                Email=form.email.data,
                enroll_time=datetime.now(),
            )

            # 验证设备ID
            if not Device.query.filter_by(Device_id=form.device_id.data).first():
                user_.Device_id = '未知设备'

            try:
                db.session.add(user_)
                db.session.commit()
                flash('注册成功！请登录。', 'success')
                return redirect(url_for('login'))
            except IntegrityError:
                db.session.rollback()
                flash('账号或设备 ID 已被注册，请尝试其他值。', 'danger')

        for field, errors in form.errors.items():
            for error in errors:
                flash(f"{getattr(form, field).label.text}: {error}", 'error')
        return render_template('enroll.html', form=form)

    form = RegistrationForm()
    return render_template('enroll.html', form=form)