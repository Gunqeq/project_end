from flask import Flask, render_template, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return render_template('index.html')

@app.route('/chat', methods=['POST'])
def chat():
    data = request.get_json(silent=True)
    if not data or 'message' not in data:
        return jsonify({'response': 'Error: invalid request'}), 400
        
    user_message = data.get('message', '').lower()
    
    # Simple echo/rule-based logic
    if 'hello' in user_message or 'hi' in user_message or 'สวัสดี' in user_message:
        bot_response = "Hello! How can I help you today? (สวัสดีครับ มีอะไรให้ช่วยไหมครับ)"
    elif 'who are you' in user_message or 'คุณคือใคร' in user_message:
        bot_response = "I am a simple AI chatbot. (ผมคือแชทบอท AI ครับ)"
    elif 'bye' in user_message or 'บ๊ายบาย' in user_message:
        bot_response = "Goodbye! Have a nice day. (ลาก่อนครับ)"
    else:
        bot_response = f"You said: {user_message}. I'm still learning! (ระบบยังเรียนรู้อยู่ครับ)"

    return jsonify({'response': bot_response})

if __name__ == '__main__':
    app.run(debug=True)
