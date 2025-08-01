from flask import (
    Flask,
    request,
    jsonify,
    redirect,
    render_template,
    send_from_directory,
)
from flask_cors import CORS
from flask_socketio import SocketIO, emit
import subprocess
import json
import os, time
import sys

app = Flask(__name__, static_folder="static", static_url_path="/static")


# 添加output目录的静态文件访问
@app.route("/output/<path:filename>")
def output_file(filename):
    return send_from_directory(os.path.join(os.getcwd(), "output"), filename)


socketio = SocketIO(app)
CORS(
    app,
    resources={
        r"/*": {
            "origins": "*",
            "methods": ["GET", "POST", "PUT", "DELETE", "OPTIONS"],
            "allow_headers": ["Content-Type", "Authorization"],
            "expose_headers": ["Content-Type"],
            "supports_credentials": True,
            "max_age": 600,
        }
    },
)  # 启用CORS支持

# 配置文件路径
CONFIG_PATH = os.path.join(os.path.dirname(__file__), "config", "config.json")


def parse_channels():
    """解析sctv.txt文件内容"""
    channels = []
    try:
        with open("output/sctv.txt", "r", encoding="utf-8") as f:
            for line in f:
                if line.strip() and not line.startswith("#") and "#genre#" not in line:
                    # 格式：频道名称,rtsp地址#组播地址
                    parts = line.strip().replace("#", ",").split(",")
                    if len(parts) >= 3:
                        name = parts[0].strip()
                        rtsp = (
                            parts[1].strip()
                            if "rtsp" in parts[1].strip()
                            else parts[2].strip()
                        )
                        multicast = (
                            parts[2].strip()
                            if "rtsp" not in parts[2].strip()
                            else parts[1].strip()
                        )
                        channels.append(
                            {"name": name, "rtsp_url": rtsp, "multicast_url": multicast}
                        )
    except FileNotFoundError:
        pass  # 文件不存在时返回空列表
    return channels


def config_exists():
    """检查配置文件是否存在"""
    return os.path.exists(CONFIG_PATH)


@app.route("/")
def index():
    if not config_exists():
        return redirect("/config")
    return redirect("/channels")


@app.route("/channels")
def channels():
    channels = parse_channels()
    if not channels:
        return render_template(
            "index.html", channels=[], message="当前没有频道数据，请点击手动更新"
        )
    return render_template("index.html", channels=channels)


@app.route("/config")
def config():
    return render_template("config.html")


@app.route("/save_config", methods=["POST"])
def save_config():
    try:
        config_data = request.json

        # 添加默认UserAgent
        config_data["UserAgent"] = (
            "B700-V2A|Mozilla|5.0|ztebw(Chrome)|1.2.0;Resolution(PAL,720p,1080i) AppleWebKit/535.7 (KHTML, like Gecko) Chrome/16.0.912.63 Safari/535.7"
        )

        # 确保config目录存在
        config_dir = os.path.dirname(CONFIG_PATH)
        if not os.path.exists(config_dir):
            os.makedirs(config_dir)

        # 保存配置到文件
        with open(CONFIG_PATH, "w", encoding="utf-8") as f:
            json.dump(config_data, f, ensure_ascii=False, indent=4)

        return jsonify({"success": True, "message": "配置保存成功"})
    except Exception as e:
        return jsonify({"success": False, "message": str(e)}), 500


@app.route("/run_script", methods=["GET"])
def run_script():
    """手动运行更新脚本"""
    try:
        # 检查脚本文件是否存在
        script_path = os.path.join(
            os.path.dirname(__file__), "get_iptv_channels_V1.1.py"
        )
        if not os.path.exists(script_path):
            return (
                jsonify({"success": False, "error": f"脚本文件 {script_path} 不存在"}),
                404,
            )

        # 使用虚拟环境的python解释器
        python_path = sys.executable
        if not os.path.exists(python_path):
            return (
                jsonify(
                    {"success": False, "error": f"Python解释器 {python_path} 不存在"}
                ),
                404,
            )

        # 启动后台任务运行脚本并发送日志
        socketio.start_background_task(
            target=run_script_with_logging,
            script_path=script_path,
            python_path=python_path,
        )
        return jsonify({"success": True, "message": "脚本开始运行"})
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


def run_script_with_logging(script_path, python_path):
    """运行脚本并实时发送日志"""
    try:
        # 设置环境变量PYTHONUNBUFFERED=1确保实时输出
        time.sleep(2)
        process = subprocess.Popen(
            [python_path, script_path],
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            encoding="utf-8",
            universal_newlines=True,
            env={**os.environ, "PYTHONUNBUFFERED": "1"},
        )

        import threading

        def read_stream(stream, stream_type):
            """读取流并发送日志"""
            while True:
                output = stream.readline()
                if output:
                    socketio.emit("log", {"data": output.strip(), "type": stream_type})
                else:
                    break

        # 创建线程分别读取stdout和stderr
        stdout_thread = threading.Thread(
            target=read_stream, args=(process.stdout, "stdout")
        )
        stderr_thread = threading.Thread(
            target=read_stream, args=(process.stderr, "stderr")
        )

        # 启动线程
        stdout_thread.start()
        stderr_thread.start()

        # 等待线程完成
        stdout_thread.join()
        stderr_thread.join()

        # 发送脚本完成状态
        if process.returncode == None:
            socketio.emit("script_complete")
        else:
            socketio.emit(
                "script_failed", {"error": f"脚本退出代码: {process.returncode}"}
            )

        return process.returncode == 0
    except Exception as e:
        socketio.emit("script_failed", {"error": str(e)})
        return False


@socketio.on("connect")
def handle_connect():
    emit("log", {"data": "WebSocket连接成功"})


def setup_cron_job(cron_expression):
    """设置crontab定时任务"""
    try:
        # 获取当前脚本路径
        project_path = os.path.dirname(__file__)
        script_path = os.path.join(
            os.path.dirname(__file__), "get_iptv_channels_V1.1.py"
        )
        python_path = sys.executable

        # 验证cron表达式格式
        fields = cron_expression.split()
        if len(fields) != 5:
            return False, "cron表达式必须包含5个字段"

        # 修改后的验证逻辑
        def is_valid_cron_field(field):
            # 检查是否只包含有效字符
            for char in field:
                if not (char.isdigit() or char in ["*", "/", "-", ","]):
                    return False
            return True

        if not all(is_valid_cron_field(field) for field in fields):
            return False, "无效的cron表达式格式"

        # 构建cron命令
        cron_command = (
            f"{cron_expression} cd {project_path} && {python_path} {script_path}"
        )

        # 获取当前crontab内容
        process = subprocess.run(
            ["crontab", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )

        # 检查crontab命令是否成功
        stderr_output = process.stderr.decode("utf-8")
        if process.returncode != 0:
            if "no crontab for" in stderr_output:
                # 没有crontab，使用空内容
                cron_content = ""
            elif "permission denied" in stderr_output.lower():
                return False, "没有权限访问crontab，请使用sudo运行"
            else:
                return False, f"获取crontab失败: {stderr_output}"
        else:
            cron_content = process.stdout.decode("utf-8")

        # 检查是否已存在相同任务
        if cron_command in cron_content:
            return True, "定时任务已存在"

        # 添加新任务
        new_cron = cron_content + "\n" + cron_command + "\n"
        process = subprocess.run(
            ["crontab", "-"],
            input=new_cron.encode("utf-8"),
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # 检查crontab写入是否成功
        if process.returncode != 0:
            return False, f"写入crontab失败: {process.stderr.decode('utf-8')}"

        return True, "定时任务添加成功"
    except Exception as e:
        import traceback

        return False, f"设置定时任务时发生错误: {str(e)}\n{traceback.format_exc()}"


@app.route("/set_cron", methods=["POST"])
def set_cron():
    """设置定时任务"""
    try:
        # 打印请求头信息
        print("Request headers:", request.headers)
        print("Content-Type:", request.headers.get("Content-Type"))

        # 检查请求头是否为JSON
        if not request.is_json:
            print("Invalid content type")
            return (
                jsonify({"success": False, "error": "请求头必须为application/json"}),
                400,
            )

        # 打印请求体
        print("Request data:", request.data)

        data = request.get_json()
        print("Parsed JSON:", data)

        if not data:
            print("No JSON data received")
            return jsonify({"success": False, "error": "未接收到有效数据"}), 400

        cron_expression = data.get("cron_expression")

        if not cron_expression:
            print("Missing cron_expression")
            return jsonify({"success": False, "error": "请输入有效的cron表达式"}), 400

        print("Cron expression:", cron_expression)
        success, message = setup_cron_job(cron_expression)
        return jsonify({"success": success, "message": message})
    except Exception as e:
        print("Error:", str(e))
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/get_cron", methods=["GET"])
def get_cron():
    """获取当前定时任务"""
    try:
        process = subprocess.run(
            ["crontab", "-l"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if process.returncode != 0:
            return jsonify(
                {
                    "success": True,
                    "cron_expression": None,
                    "message": "没有设置定时任务",
                }
            )

        cron_content = process.stdout.decode("utf-8")
        # 查找当前脚本的定时任务
        script_path = os.path.join(
            os.path.dirname(__file__), "get_iptv_channels_V1.1.py"
        )
        for line in cron_content.splitlines():
            if script_path in line:
                # cron_expression = line.split(script_path)[0].strip()
                return jsonify({"success": True, "cron_expression": line})

        return jsonify(
            {"success": True, "cron_expression": None, "message": "没有找到定时任务"}
        )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


@app.route("/delete_cron", methods=["POST", "DELETE"])
def delete_cron():
    """删除定时任务"""
    try:
        process = subprocess.run(
            ["crontab", "-r"], stdout=subprocess.PIPE, stderr=subprocess.PIPE
        )
        if process.returncode == 0:
            return jsonify({"success": True, "message": "定时任务已删除"})
        else:
            return (
                jsonify({"success": False, "error": process.stderr.decode("utf-8")}),
                500,
            )
    except Exception as e:
        return jsonify({"success": False, "error": str(e)}), 500


if __name__ == "__main__":
    socketio.run(app, host="0.0.0.0", port=5000, debug=True, allow_unsafe_werkzeug=True)
