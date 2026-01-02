
import requests
import json
import os

headers = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
    'Accept-Language': 'en-US,en;q=0.9',
    'Accept': 'application/json, text/plain, */*'
}

def fetch_quarterly():
    url = 'https://api.nasdaq.com/api/company/AAPL/financials?frequency=2'
    print(f"Fetching: {url}")
    try:
        response = requests.get(url, headers=headers, timeout=30)
        if response.status_code == 200:
            data = response.json()
            if 'data' in data and data['data']:
                with open("fresh_nasdaq_quarterly.json", "w", encoding="utf-8") as f:
                    json.dump(data, f, indent=4)
                print("Saved to fresh_nasdaq_quarterly.json")
                
                dump_str = json.dumps(data)
                if "18257" in dump_str:
                    print("Found 18257 in Quarterly data!")
                elif "18,257" in dump_str:
                    print("Found 18,257 in Quarterly data!")
                
                if "211" in dump_str:
                    print("Found 211 in Quarterly data!")
            else:
                print("No 'data' content in response.")
        else:
            print(f"Failed with status: {response.status_code}")
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    fetch_quarterly()
