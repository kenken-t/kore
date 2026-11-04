import os
import time
import random
import sys
import json
from datetime import datetime as dt
from selenium import webdriver
from selenium.common.exceptions import WebDriverException, TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service

# --- 設定の読み込み ---
def load_settings():
    # GitHub Secrets（環境変数）から取得するか、ローカルの config.json を参照する
    config_env = os.getenv('RAKUTEN_CONFIG_JSON')
    
    if config_env:
        # GitHub Actions 実行時
        try:
            return json.loads(config_env)
        except json.JSONDecodeError:
            print("Error: GitHub Secrets の形式が正しくありません。")
            sys.exit(1)
    else:
        # ローカル実行時
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print("Error: config.json または GitHub Secrets が設定されていません。")
            sys.exit(1)

def load_tags():
    try:
        with open('tags.txt', 'r', encoding='utf-8') as f:
            # カンマ区切りと改行の両方に対応
            content = f.read().replace('\n', ',')
            return [word.strip() for word in content.split(',') if word.strip()]
    except FileNotFoundError:
        return ["楽天"] # フォールバック

# 設定の初期化
config = load_settings()
taglist = load_tags()

# --- WebDriver設定 ---
options = webdriver.chrome.options.Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1280,1000')

# ユーザーデータ（プロファイル）の指定（環境に応じて変更）
user_data_dir = config.get("user_data_dir")
if user_data_dir and os.path.exists(user_data_dir):
    options.add_argument(f'--user-data-dir={user_data_dir}')

# Driverの起動（GitHub Actions では PATH が通っているため service 指定なしで動くことが多い）
driver = webdriver.Chrome(options=options)

def click_button(button_id):
    # 言語切り替えの案内バナーがボタンに重なってクリックできないため、取り除いてから押す
    driver.execute_script("document.querySelectorAll('r10-language-disclaimer').forEach(e => e.remove());")
    button = driver.find_element(By.ID, button_id)
    try:
        button.click()
    except WebDriverException:
        driver.execute_script("arguments[0].click();", button)

def login():
    try:
        print("ログインを開始します...")
        driver.get('https://room.rakuten.co.jp/common/login?redirectafterlogin=/items')

        # ユーザー名入力
        username_field = WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.NAME, 'username')))
        username_field.clear()
        username_field.send_keys(config["email"])
        time.sleep(1)
        click_button('cta001')

        # パスワード入力
        # パスワード欄は Selenium から「非表示」と判定されることがあるので、パスワード画面の「次へ」が出るのを待つ
        WebDriverWait(driver, 15).until(lambda d: d.find_element(By.ID, 'cta011').is_displayed())
        password_field = driver.find_element(By.NAME, 'password')
        try:
            password_field.clear()
            password_field.send_keys(config["password"])
        except WebDriverException:
            driver.execute_script(
                "const el = arguments[0];"
                "Object.getOwnPropertyDescriptor(HTMLInputElement.prototype, 'value').set.call(el, arguments[1]);"
                "el.dispatchEvent(new Event('input', {bubbles: true}));"
                "el.dispatchEvent(new Event('change', {bubbles: true}));",
                password_field, config["password"])
        time.sleep(1)
        click_button('cta011')
        print("パスワードを送信しました")

        # ROOMに戻ってこられたらログイン成功
        back_to_room = lambda d: d.current_url.startswith('https://room.rakuten.co.jp/') and '/login' not in d.current_url
        try:
            WebDriverWait(driver, 30).until(back_to_room)
        except TimeoutException:
            # 楽天側のログイン後の転送画面（#/redirect）で止まることがあるので、
            # ログイン済みの状態でROOMのログインURLを開き直して戻ってくる
            print(f"転送で止まったため開き直します（{driver.current_url.split('#')[-1]}）")
            driver.get('https://room.rakuten.co.jp/common/login?redirectafterlogin=/items')
            WebDriverWait(driver, 30).until(back_to_room)
        print(f"ログインしました: {driver.current_url}")
        return True
    except Exception as e:
        print(f"ログインエラー: {e}")
        print(f"現在のURL: {driver.current_url}")
        # 原因調査用に、画面上の入力欄とボタンの状態を出しておく
        for el in driver.find_elements(By.CSS_SELECTOR, 'input, [role="button"]'):
            print(f"  {el.tag_name} id={el.get_attribute('id')} name={el.get_attribute('name')} type={el.get_attribute('type')} 表示={el.is_displayed()} 文字={el.text[:20]!r}")
        return False

def search():
    try:
        tag = random.choice(taglist)
        print(f"検索キーワード: {tag}")
        search_url = f'https://room.rakuten.co.jp/search/item?keyword={tag}&original_photo=1'
        driver.get(search_url)
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.item-navigation.ng-scope')))
    except Exception as e:
        print(f"検索エラー: {e}")

def like(set_num):
    cnt = 0
    num = 0
    while set_num > cnt:
        try:
            # スクロールして要素を読み込み
            scroll_check = 0
            while len(driver.find_elements(By.CSS_SELECTOR, '.item-navigation.ng-scope')) <= num:
                if scroll_check >= 5: return cnt
                driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
                scroll_check += 1
                time.sleep(4)

            items = driver.find_elements(By.CSS_SELECTOR, '.item-navigation.ng-scope')
            like_button = items[num].find_elements(By.TAG_NAME, 'a')[1]
            
            if 'isLiked' not in like_button.get_attribute('class'):
                like_button.click()
                # 上限チェック
                if len(driver.find_elements(By.CSS_SELECTOR, '.dialog-container')) > 0:
                    print("上限に達しました。")
                    break
                cnt += 1
                if cnt % 5 == 0: print(f"進捗: {cnt} 件完了")
                time.sleep(random.randint(6, 12))
            else:
                time.sleep(0.5)
            num += 1
        except Exception:
            num += 1
            continue
    return cnt

if __name__ == '__main__':
    print(f"--- 実行開始: {dt.now()} ---")
    try:
        if not login():
            # ログインできないまま「成功」扱いにならないよう、失敗で終わらせる
            sys.exit(1)
        search()
        target = random.randint(90, 100)
        result = like(target)
        print(f"最終結果: {result} 商品に「いいね」しました。")
    finally:
        driver.quit()
        print(f"--- 終了: {dt.now()} ---")
      
