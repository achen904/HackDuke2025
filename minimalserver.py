# minimal_server.py (example of adding imports)
print("BEFORE FLASK IMPORT")
from flask import Flask, request, jsonify # This is fine
print("AFTER FLASK IMPORT, BEFORE CORS")
from flask_cors import CORS             # Does it fail here?
print("AFTER CORS, BEFORE AST")
import ast                              # Or here?
print("AFTER AST, BEFORE AGENT")
from agent import agent as duke_agent_instance # Or here?
print("AFTER AGENT IMPORT")

app = Flask(__name__)
CORS(app)
# ... rest of the minimal app