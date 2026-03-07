import os
import json
import re
import requests
from flask import Flask, request, jsonify
import yfinance as yf

app = Flask(__name__)

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

@app.route('/check_price', methods=['GET'])
def check_price():
    current_price = get_gold_price()
    if not isinstance(current_price, float):
        return f"Keep alive active. Error detail {current_price}", 200

    msg = ""
    if STATE["buy"] > 0 and current_price <= STATE["buy"]:
        msg = f"买入提醒\n当前金价 {current_price} 已降至目标价 {STATE['buy']} 及其以下"
        STATE["buy"] = 0.0
    elif STATE["sell"] < 9999.0 and current_price >= STATE["sell"]:
        msg = f"卖出提醒\n当前金价 {current_price} 已涨至目标价 {STATE['sell']} 及其以上"
        STATE["sell"] = 9999.0 

    if msg and STATE["chat_id"]:
        send_lark_msg(STATE["chat_id"], msg)

    return f"Checked Price {current_price}", 200

@app.route('/lark_webhook', methods=['POST'])
def lark_event():
    data = request.json
    
    if "challenge" in data:
        return jsonify({"challenge": data["challenge"]})

    if "header" in data and data["header"]["event_type"] == "im.message.receive_v1":
        event = data["event"]
        chat_id = event["message"]["chat_id"]
        STATE["chat_id"] = chat_id

        msg_content = json.loads(event["message"]["content"])
        text = msg_content.get("text", "")

        reply_msg = ""
        if "买入" in text:
            match = re.search(r'买入\s*(\d+(?:\.\d+)?)', text)
            if match:
                STATE["buy"] = float(match.group(1))
                reply_msg = f"设置成功 当前买入提醒价 {STATE['buy']}"
        elif "卖出" in text:
            match = re.search(r'卖出\s*(\d+(?:\.\d+)?)', text)
            if match:
                STATE["sell"] = float(match.group(1))
                reply_msg = f"设置成功 当前卖出提醒价 {STATE['sell']}"
        elif "查询" in text:
            current_price = get_gold_price()
            if isinstance(current_price, float):
                reply_msg = f"当前监控状态\n当前实时金价 {current_price}\n买入提醒设置 {STATE['buy']}\n卖出提醒设置 {STATE['sell']}"
            else:
                reply_msg = f"数据获取异常\n错误详情 {current_price}\n买入提醒设置 {STATE['buy']}\n卖出提醒设置 {STATE['sell']}"

        if reply_msg:
            send_lark_msg(chat_id, reply_msg)

    return jsonify({"msg": "ok"})

@app.route('/check_price', methods=['GET'])
def check_price():
    current_price = get_gold_price()
    if not isinstance(current_price, float):
        return f"Fail {current_price}", 500

    msg = ""
    if STATE["buy"] > 0 and current_price <= STATE["buy"]:
        msg = f"买入提醒\n当前金价 {current_price} 已降至目标价 {STATE['buy']} 及其以下"
        STATE["buy"] = 0.0
    elif STATE["sell"] < 9999.0 and current_price >= STATE["sell"]:
        msg = f"卖出提醒\n当前金价 {current_price} 已涨至目标价 {STATE['sell']} 及其以上"
        STATE["sell"] = 9999.0 

    if msg and STATE["chat_id"]:
        send_lark_msg(STATE["chat_id"], msg)

    return f"Checked Price {current_price}", 200

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=int(os.environ.get('PORT', 5000)))

