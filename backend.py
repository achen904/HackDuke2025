from flask import Flask, request, jsonify

app = Flask(__name__)

@app.route('/')
def home():
    return "Flask server is running."

@app.route('/predict', methods=['POST'])
def predict():
    data = request.json
    user_input = data.get("input", "")
    # Placeholder response
    response = f"Echo: {user_input}"
    return jsonify({"response": response})

if __name__ == '__main__':
    app.run(debug=True)