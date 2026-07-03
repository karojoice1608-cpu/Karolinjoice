import requests
s = requests.Session()
s.post('http://localhost:8000/login', data={'username': 'admin', 'password': 'password'}, allow_redirects=True)
resp = s.get('http://localhost:8000/api/images/?page=1&page_size=2')
print("Status:", resp.status_code)
try:
    for img in resp.json()[:2]:
        print(f"ID: {img.get('id')} - Subject: {img.get('subject')}")
except Exception as e:
    print(e)
