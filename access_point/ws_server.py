#!/usr/bin/env python
from logging import raiseExceptions
from flask import Flask, request, jsonify, make_response, render_template

app = Flask(__name__)

@app.route("/")
def index():
    return render_template('index.html')

@app.route("/publisher/registration", methods=['get', 'post'])
def publisher_registration():
    if request.method == 'GET':
        return render_template('create_publisher.html')  
    else:
        return make_response(jsonify(request.json), 200)

@app.route("/subscriber/registration", methods=['get', 'post'])
def subscriber_registration():
    if request.method == "GET":
        return render_template('create_subscriber.html')
    else:
        res = {}
        res['query_id'] = 'blabla123'
        return make_response(jsonify(res), 200)

@app.route("/subscribe/query/<string:query_id>", methods=['get'])
def query_detail(query_id):
    return render_template('query_detail.html', **{'query_id': query_id})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8080, debug=True)


































































































# from http.server import BaseHTTPRequestHandler, HTTPServer
# import json
# import cgi

# hostName = "localhost"
# serverPort = 8080

# class HTTPHandler(BaseHTTPRequestHandler):

#     def _set_headers(self):
#         self.send_response(200)
#         self.send_header('Content-type', 'application/json')
#         self.send_header('Access-Control-Allow-Credentials', 'true')
#         self.send_header('Access-Control-Allow-Origin', '*')
#         self.send_header('Access-Control-Allow-Methods', 'GET, POST, OPTIONS')
#         self.send_header("Access-Control-Allow-Headers", "X-Requested-With, Content-type")
#         self.end_headers()
        
#     def do_HEAD(self):
#         self._set_headers()
        
#     # GET sends back a Hello world message
#     def do_GET(self):
#         self._set_headers()
#         self.wfile.write(json.dumps({'hello': 'world', 'received': 'ok'}))

#     def do_OPTIONS(self):
#         self._set_headers()

#     def do_POST(self):
#         ctype, pdict = cgi.parse_header(self.headers.get('content-type'))
        
#         # refuse to receive non-json content
#         if ctype != 'application/json':
#             self.send_response(400)
#             self.end_headers()
#             return
            
#         # read the message and convert it into a python dictionary
#         length = int(self.headers.get('content-length'))
#         message = json.loads(self.rfile.read(length))
        
#         # add a property to the object, just to mess with data
#         message['received'] = 'ok'
        
#         # send the message back
#         self._set_headers()
#         self.wfile.write(str.encode(json.dumps(message)))


# if __name__ == "__main__":        
#     webServer = HTTPServer((hostName, serverPort), HTTPHandler)
#     print("Server started http://%s:%s" % (hostName, serverPort))

#     try:
#         webServer.serve_forever()
#     except KeyboardInterrupt:
#         pass

#     webServer.server_close()
#     print("Server stopped.")