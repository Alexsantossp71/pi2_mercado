import httpx
import os
from dotenv import load_dotenv

load_dotenv()
token = os.environ.get('TURSO_AUTH_TOKEN')
url = 'https://dispensa-alex-santos-sp.aws-us-east-1.turso.io/v1/execute'
headers = {'Authorization': f'Bearer {token}'}
payload = {
    'stmt': {
        'sql': 'SELECT COUNT(*) FROM produtos p WHERE (p.id IN (SELECT id FROM produtos_fts WHERE produtos_fts MATCH ?) OR LOWER(p.nome) LIKE ? OR LOWER(p.marca) LIKE ?);',
        'args': [{'type':'text', 'value':'"arroz"*'}, {'type':'text', 'value':'%arroz%'}, {'type':'text', 'value':'%arroz%'}]
    }
}
res = httpx.post(url, headers=headers, json=payload)
print(res.text)
