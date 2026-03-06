from flask import Flask, request, jsonify
import requests
import json
import os
import re

app = Flask(__name__)

# 在内存中存储当前设定的价格和群聊ID
STATE = {
    "buy": 0.0,
    "sell": 9999.0,
    "chat_id": "" 
}

APP_ID = os.environ.get("APP_ID", "")
APP_SECRET = os.environ.get("APP_SECRET", "")

def get_tenant_access_token():
    url = "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal"
    req = requests.post(url, json={"app_id": APP_ID, "app_secret": APP_SECRET})
    return req.json().get("tenant_access_token", "")

def send_lark_msg(chat_id, text):
    token = get_tenant_access_token()
    url = "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id"
    headers = {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}
    payload = {"receive_id": chat_id, "msg_type": "text", "content": json.dumps({"text": text})}
    requests.post(url, headers=headers, json=payload)

def get_gold_price():
    try:
        url = "http://hq.sinajs.cn/list=sge_au9999"
        headers = {
            "Referer": "https://finance.sina.com.cn",
            "User-Agent": "Mozilla/5.0 Windows NT 10.0; Win64; x64 AppleWebKit/537.36"
        }
        response = requests.get(url, headers=headers, timeout=5)
        data = response.text.split(",")
        if len(data) > 3:
            return float(data[2])
    except Exception:
        pass
    return None

# 用于接收飞书消息的接口
@app.route('/lark_webhook', methods=['POST'])
def lark_event():
    data = request.json
    
    # 飞书首次配置时的 URL 验证
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})

    # 处理接收到的对话指令
    if "header" in data and data["header"]["event_type"] == "im.message.receive_v1":
        event = data["event"]
        chat_id = event["message"]["chat_id"]
        STATE["chat_id"] = chat_id  # 记住你在哪个群里发消息，就在哪个群里报警

        msg_content = json.loads(event["message"]["content"])
        text = msg_content.get("text", "")

        reply_msg = ""
        if "买入" in text:
            match = re.search(r'买入\s*(\d+(?:\.\d+)?)', text)
            if match:
                STATE["buy"] = float(match.group(1))
                reply_msg = f"✅ 设置成功 当前买入提醒价 {STATE['buy']}"
        elif "卖出" in text:
            match = re.search(r'卖出\s*(\d+(?:\.\d+)?)', text)
            if match:
                STATE["sell"] = float(match.group(1))
                reply_msg = f"✅ 设置成功 当前卖出提醒价 {STATE['sell']}"
        elif "查询" in text:
            reply_msg = f"📊 当前监控设置\n买入提醒价 {STATE['buy']}\n卖出提醒价 {STATE['sell']}"
            
        if reply_msg:
            send_lark_msg(chat_id, reply_msg)

    return jsonify({"msg": "ok"})

# 用于1分钟定时触发检测的接口
@app.route('/check_price', methods=['GET'])
def check_price():
    current_price = get_gold_price()
    if not current_price:
        return "Fail", 500

    msg = ""
    # 判断是否到达目标价
    if STATE["buy"] > 0 and current_price <= STATE["buy"]:
        msg = f"🚨 【买入提醒】\n当前金价 {current_price} 已降至目标价 {STATE['buy']} 及其以下！"
        STATE["buy"] = 0.0  # 触发后重置，防止每分钟疯狂发送
    elif STATE["sell"] < 9999.0 and current_price >= STATE["sell"]:
        msg = f"🚨 【卖出提醒】\n当前金价 {current_price} 已涨至目标价 {STATE['sell']} 及其以上！"
        STATE["sell"] = 9999.0 

    if msg and STATE["chat_id"]:
        send_lark_msg(STATE["chat_id"], msg)

    return f"Checked. Price: {current_price}", 200

if __name__ == '__main__':

    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))
