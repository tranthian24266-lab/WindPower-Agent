import urllib.request
import json
import uuid

boundary = '----WebKitFormBoundary' + uuid.uuid4().hex

with open(r'C:\Users\luzian\Desktop\littlemodel\fault_diagnosis\test_data\test_sensor1_x.npy', 'rb') as f:
    data = f.read()

body = (
    f"--{boundary}\r\n"
    f"Content-Disposition: form-data; name=\"file\"; filename=\"test_sensor1_x.npy\"\r\n"
    f"Content-Type: application/octet-stream\r\n\r\n"
).encode() + data + f"\r\n--{boundary}--\r\n".encode()

req1 = urllib.request.Request(
    'http://127.0.0.1:8000/api/upload', 
    data=body, 
    headers={'Content-Type': f'multipart/form-data; boundary={boundary}'}
)
res1 = json.loads(urllib.request.urlopen(req1).read())
file_id = res1['file']['file_id']

req2 = urllib.request.Request(
    'http://127.0.0.1:8000/api/diagnose', 
    data=json.dumps({'file_id': file_id, 'task_type': 'fault_diagnosis'}).encode(), 
    headers={'Content-Type': 'application/json'}
)
res2 = json.loads(urllib.request.urlopen(req2).read())
case_id = res2['case_id']

try:
    req3 = urllib.request.Request(
        'http://127.0.0.1:8000/api/agent-runs', 
        data=json.dumps({'run_type': 'chat_answer', 'case_id': case_id, 'input': {'question': 'test'}}).encode(), 
        headers={'Content-Type': 'application/json'}
    )
    res3 = urllib.request.urlopen(req3).read()
    print("SUCCESS /api/agent-runs:", res3.decode())
except urllib.error.HTTPError as e:
    print("HTTPError /api/agent-runs:", e.code, e.read().decode())

try:
    req4 = urllib.request.Request(
        'http://127.0.0.1:8000/api/chat', 
        data=json.dumps({'case_id': case_id, 'question': 'test'}).encode(), 
        headers={'Content-Type': 'application/json'}
    )
    res4 = urllib.request.urlopen(req4).read()
    print("SUCCESS /api/chat:", res4.decode())
except urllib.error.HTTPError as e:
    print("HTTPError /api/chat:", e.code, e.read().decode())
