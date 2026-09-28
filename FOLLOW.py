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

def follow(set_num):
    # ROOM編集部のフォロワー一覧（おそらく新規順）からフォローする
    driver.get('https://room.rakuten.co.jp/room_jp/followers')
    WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.follow.icon-follow')))

    cnt = 0
    num = 0
    while set_num > cnt:
        # 要素が読み込めていない場合はスクロールして次を読み込む
        scroll_check = 0
        while len(driver.find_elements(By.CSS_SELECTOR, '.follow.icon-follow')) <= num:
            if scroll_check >= 6:  # 30秒待っても次が読み込まれなければ終了
                print("これ以上ユーザーを読み込めませんでした。")
                return cnt
            driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
            scroll_check += 1
            time.sleep(5)

        try:
            target = driver.find_elements(By.CSS_SELECTOR, '.follow.icon-follow')[num]
            # 未フォローなら「follow icon-follow」、フォロー済みなら「ng-hide」が付く
            if target.get_attribute('class').strip() == 'follow icon-follow':
                target.find_element(By.XPATH, '..').click()

                # 上限チェック
                if len(driver.find_elements(By.CSS_SELECTOR, '.dialog-container.ng-isolate-scope.modal-popup')) > 0:
                    print("上限に達しました。")
                    break

                cnt += 1
                if cnt % 5 == 0: print(f"進捗: {cnt} 人完了")
                time.sleep(random.randint(random.randint(5, 8), random.randint(10, 12)))
            else:
                time.sleep(1)
        except WebDriverException:
            pass

        num += 1
    return cnt

if __name__ == '__main__':
    print(f"--- 実行開始: {dt.now()} ---")
    try:
        login()
        target = random.randint(96, 99)
        result = follow(target)
        print(f"最終結果: {result} 人をフォローしました。")
    except Exception as e:
        print(f"エラー: {e}")
    finally:
        driver.quit()
        print(f"--- 終了: {dt.now()} ---")
