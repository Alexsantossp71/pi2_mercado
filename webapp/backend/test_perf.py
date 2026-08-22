import time
from dotenv import load_dotenv
load_dotenv()
from fastapi.testclient import TestClient
from main import app

client = TestClient(app)
times = []

print("Testando busca 'arroz' sem categoria e marca no Turso...")
try:
    client.get('/api/produtos?q=feijao')
    
    for i in range(5):
        start = time.time()
        res = client.get('/api/produtos?q=arroz&limit=20')
        end = time.time()
        if res.status_code == 200:
            times.append(end - start)
            print(f"Tentativa {i+1}: {end - start:.4f}s")
        else:
            print(f"Tentativa {i+1} falhou com status {res.status_code}: {res.text}")

    if times:
        print(f"Média de tempo: {sum(times)/len(times):.4f}s")
except Exception as e:
    print(f"Erro: {e}")
