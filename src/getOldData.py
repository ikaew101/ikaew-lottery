# services/github_data.py
import pandas as pd
import requests
import io

def fetch_old_data():
    print("📦 1. Loading Historical Data (GitHub)...")
    url = "https://raw.githubusercontent.com/heart/Data-Set-Thai-Lotto/master/lotto.csv"
    try:
        content = requests.get(url).content
        df = pd.read_csv(io.StringIO(content.decode('utf-8')))
        
        rename_map = {
            'date': 'date',
            'prize_1st': 'first_prize',
            'prize_2digits': 'last_two_digits',
            'prize_pre_3digit': 'prize_pre_3digit',
            'prize_sub_3digits': 'prize_suf_3digit'
        }
        df = df.rename(columns=rename_map)
        # เลือกคอลัมน์
        df = df[[c for c in rename_map.values() if c in df.columns]]
        df['date'] = pd.to_datetime(df['date'])
        return df
    except Exception as e:
        print(f"   ❌ Error: {e}")
        return pd.DataFrame()