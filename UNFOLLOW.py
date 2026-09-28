import os
import time
import random
import sys
import json
from datetime import datetime as dt
from selenium import webdriver
from selenium.common.exceptions import WebDriverException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# --- 設定の読み込み ---
def load_settings():
    # GitHub Secrets（環境変数）から取得するか、ローカルの config.json を参照する
    config_env = os.getenv('RAKUTEN_CONFIG_JSON')

    if config_env:
        # GitHub Actions 実行時
        try:
            data = json.loads(config_env)
        except json.JSONDecodeError:
            print("Error: GitHub Secrets の形式が正しくありません。")
            sys.exit(1)
    else:
        # ローカル実行時
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                data = json.load(f)
        except FileNotFoundError:
            print("Error: config.json または GitHub Secrets が設定されていません。")
            sys.exit(1)

    # 旧形式（アカウントのリスト）の場合は先頭を使う
    if isinstance(data, list):
        data = data[0]
    return data

# 設定の初期化
config = load_settings()

# フォロー中一覧のURL（例: https://room.rakuten.co.jp/room_xxxxxxxx/followings）
following_url = os.getenv('ROOM_FOLLOWING_URL') or config.get("url")
if not following_url:
    print("Error: フォロー中一覧のURL（config の \"url\" か ROOM_FOLLOWING_URL）が設定されていません。")
    sys.exit(1)

# --- WebDriver設定 ---
options = webdriver.chrome.options.Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1280,2000')

# ユーザーデータ（プロファイル）の指定（環境に応じて変更）
user_data_dir = config.get("user_data_dir")
if user_data_dir and os.path.exists(user_data_dir):
    options.add_argument(f'--user-data-dir={user_data_dir}')

# Driverの起動（GitHub Actions では PATH が通っているため service 指定なしで動く）
driver = webdriver.Chrome(options=options)

def login():
    try:
        print("ログインを開始します...")
        driver.get('https://room.rakuten.co.jp/common/login?redirectafterlogin=/items')
        time.sleep(3)

        # ユーザー名入力
        username_field = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, 'username')))
        username_field.send_keys(config["email"])
        driver.find_element(By.ID, 'cta001').click()
        time.sleep(2)

        # パスワード入力
        password_field = WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.NAME, 'password')))
        password_field.send_keys(config["password"])
        driver.find_element(By.ID, 'cta011').click()
        time.sleep(5)
    except Exception as e:
        print(f"ログインエラー: {e}")

def unfollow(set_num):
    driver.get(following_url)
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.active.icon-follow')))

    # フォローした時期が古い順にアンフォローするため、最下部まで読み込む
    print("フォロー中一覧を最後まで読み込みます...")
    scroll_check = 0
    num_elements = 0
    while scroll_check < 6:  # 30秒待っても増えなければ最下部とみなす
        num_elements_new = len(driver.find_elements(By.CSS_SELECTOR, '.active.icon-follow'))
        if num_elements == num_elements_new:
            scroll_check += 1
        else:
            num_elements = num_elements_new
            scroll_check = 0
        driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
        time.sleep(5)
    print(f"フォロー中: {num_elements} 人")

    # 末尾2件はROOMオフィシャルアカウント（「ROOM編集部」「ROOMお買い得探検隊」）なので残す
    unfollow_from = (num_elements - 1) - 2
    unfollow_to = max(unfollow_from - set_num, -1)
    cnt = 0
    for num in range(unfollow_from, unfollow_to, -1):
        try:
            target = driver.find_elements(By.CSS_SELECTOR, '.active.icon-follow')[num]
            target.find_element(By.XPATH, '..').click()
            cnt += 1
            if cnt % 10 == 0: print(f"進捗: {cnt} 人完了")
        except (WebDriverException, IndexError):
            continue  # 待機を飛ばして次へ

        time.sleep(random.randint(random.randint(2, 5), random.randint(6, 7)))
    return cnt

if __name__ == '__main__':
    print(f"--- 実行開始: {dt.now()} ---")
    try:
        login()
        target = random.randint(320, 340)
        result = unfollow(target)
        print(f"最終結果: {result} 人をアンフォローしました。")
    except Exception as e:
        print(f"エラー: {e}")
    finally:
        driver.quit()
        print(f"--- 終了: {dt.now()} ---")
