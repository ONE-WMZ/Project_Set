from extensions import db
from flask_wtf import FlaskForm
from wtforms import StringField, PasswordField, IntegerField, validators

# __________________________________________________________________________________________________用户表
class User(db.Model):
    __tablename__ = 'user_info'
    ID = db.Column(db.String(255), primary_key=True)
    Account = db.Column(db.String(255), unique=True)
    Password = db.Column(db.String(255), unique=True)
    Name = db.Column(db.String(255))
    Age = db.Column(db.Integer)
    Phone = db.Column(db.String(255), unique=True)
    Device_id = db.Column(db.String(255), unique=True)
    Email = db.Column(db.String(255), unique=True)
    enroll_time = db.Column(db.DateTime)  # 改为 DateTime 更实用
    def to_dict(self):
        # 自定义序列化方法
        return {
            'ID': self.ID,
            'Account': self.Account,
            'Password': self.Password,
            'Name': self.Name,
            'Age': self.Age,
            'Phone': self.Phone,
            'Device_id': self.Device_id,
            'Email': self.Email,
            'enroll_time': self.enroll_time.isoformat() if self.enroll_time else None
            # 使用 isoformat() 将 datetime 转换为字符串
        }

# __________________________________________________________________________________________________设备表
class Device(db.Model):
    __tablename__ = 'user_device'
    Device_id = db.Column(db.String(255), primary_key=True)
    def to_dict(self):
        # 自定义序列化方法
        return {
            'Device_id': self.Device_id,
        }

# __________________________________________________________________________________________________历史表
class User_history(db.Model):
    __tablename__ = 'user_history'
    num_id = db.Column(db.Integer, primary_key=True, autoincrement=True)  # 新增自增主键
    Device_id = db.Column(db.String(255))
    user_data = db.Column(db.Integer)
    position_x = db.Column(db.Float)
    position_y = db.Column(db.Float)
    time_stamp = db.Column(db.DateTime)
    def to_dict(self):
        # 自定义序列化方法
        return {
            'num_id': self.num_id,
            'Device_id': self.Device_id,
            'user_data': self.user_data,
            'position_x': self.position_x,
            'position_y': self.position_y,
            'time_stamp': self.time_stamp,
        }


# __________________________________________________________________________________________________注册表
class RegistrationForm(FlaskForm):
    account = StringField('账号', [
        validators.DataRequired(message='账号不能为空'),
        validators.Length(min=4, max=20, message='账号长度应在4-20个字符之间')
    ])
    password = PasswordField('密码', [
        validators.DataRequired(message='密码不能为空'),
        validators.Length(min=6, message='密码长度至少6位')
    ])
    confirm_password = PasswordField('确认密码', [
        validators.DataRequired(message='请确认密码'),
        validators.EqualTo('password', message='两次输入的密码不一致')
    ])
    name = StringField('姓名', [validators.DataRequired(message='姓名不能为空')])
    age = IntegerField('年龄', [validators.Optional()])
    phone = StringField('手机号', [validators.Optional()])
    email = StringField('邮箱', [validators.Optional(), validators.Email(message='请输入有效的邮箱地址')])
    device_id = StringField('设备序列号', [validators.Optional()])


# ______________________________________________________________________________________________________________

