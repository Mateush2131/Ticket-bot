import requests

API_URL = "https://catswill.casino/api/bot/create-user"
TOKEN = "SUPER_SECRET_TOKEN_123"

def test_api():
    payload = {
        "token": TOKEN,
        "name": "TestUser",
        "email": "test123@test.com",
        "password": "TestPass123"
    }
    
    try:
        print(f"Отправка запроса на {API_URL}")
        print(f"Payload: {payload}")
        
        r = requests.post(API_URL, json=payload, timeout=20)
        
        print(f"\nСтатус: {r.status_code}")
        print(f"Ответ: {r.text[:500]}")
        
        if r.status_code == 200:
            print("\n✅ API РАБОТАЕТ!")
        else:
            print(f"\n❌ API вернул ошибку {r.status_code}")
            
    except Exception as e:
        print(f"\n❌ Ошибка: {e}")

if __name__ == "__main__":
    test_api()