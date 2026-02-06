import sqlite3
import sys
sys.stdout.reconfigure(encoding='utf-8')

conn = sqlite3.connect(r'C:\Users\tomer\AppData\Local\JobiAI\jobiai.db')
cur = conn.cursor()

print("=== HEBREW NAMES ===")
try:
    cur.execute('SELECT english_name, hebrew_name FROM hebrew_names ORDER BY english_name')
    for row in cur.fetchall():
        print(f"{row[0]}|{row[1]}")
except Exception as e:
    print(f"Error: {e}")

print("\n=== SITE SELECTORS ===")
try:
    cur.execute('SELECT domain, site_type, company_name, platform_name, url_pattern, example_company FROM site_selectors ORDER BY domain')
    for row in cur.fetchall():
        print(f"domain={row[0]}, type={row[1]}, company={row[2]}, platform={row[3]}, pattern={row[4]}, example={row[5]}")
except Exception as e:
    print(f"Error: {e}")

conn.close()
