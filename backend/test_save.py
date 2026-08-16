import requests

payload = {
  "merchant_name": "Test Merchant from Python",
  "total_amount": 42.50,
  "items": [
    {
      "item_name": "Test Item 1",
      "total_price": 40.00
    },
    {
      "item_name": "Tax Item",
      "total_price": 2.50
    }
  ]
}

res = requests.post("http://localhost:8000/api/receipts", json=payload)
print(res.status_code)
print(res.json())
