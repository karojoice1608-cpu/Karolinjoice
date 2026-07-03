import requests

s = requests.Session()

# Step 1: Login
resp = s.post(
    'http://localhost:8000/login',
    data={'username': 'admin', 'password': 'password'},
    allow_redirects=True
)
print('Login status:', resp.status_code, resp.url)

# Step 2: Try calling /api/images/ and catch any crash
try:
    resp2 = s.get('http://localhost:8000/api/images/?page=1&page_size=12')
    print('/api/images/ HTTP status:', resp2.status_code)
    print('Response text (first 1000 chars):', resp2.text[:1000])
except Exception as e:
    print('API call FAILED with error:', type(e).__name__, str(e))

# Step 3: Stats
try:
    resp3 = s.get('http://localhost:8000/api/search/stats')
    print('\n/api/search/stats HTTP status:', resp3.status_code)
    print(resp3.text[:500])
except Exception as e:
    print('Stats FAILED with error:', type(e).__name__, str(e))
