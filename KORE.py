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
    # GitHub Secrets（環境変数）またはローカルの config.json を参照
    config_env = os.getenv('RAKUTEN_CONFIG_JSON')
    if config_env:
        try:
            return json.loads(config_env)
        except json.JSONDecodeError:
            print("Error: GitHub Secrets の形式が正しくありません。")
            sys.exit(1)
    else:
        try:
            with open('config.json', 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            print("Error: config.json または GitHub Secrets が設定されていません。")
            sys.exit(1)

config = load_settings()

# --- WebDriver設定 ---
options = webdriver.chrome.options.Options()
options.add_argument('--headless')
options.add_argument('--no-sandbox')
options.add_argument('--disable-dev-shm-usage')
options.add_argument('--window-size=1280,1000')

# 実行環境に合わせたプロファイル設定
if config.get("user_data_dir") and os.path.exists(config["user_data_dir"]):
    options.add_argument(f'--user-data-dir={config["user_data_dir"]}')

driver = webdriver.Chrome(options=options)
driver.implicitly_wait(10)

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
        # config.json 内の keyword を使用
        tag = config.get("keyword", "楽天")
        print(f"検索ワード: {tag}")
        search_url = f'https://room.rakuten.co.jp/search/item?keyword={tag}&original_photo=0'
        driver.get(search_url)
        WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.item-navigation.ng-scope')))
        return tag
    except Exception as e:
        print(f"検索エラー: {e}")
        return None

def kore(set_num):
    cnt = 0
    num = 0
    while set_num > cnt:
        try:
            # 次の要素までスクロール
            scroll_check = 0
            while len(driver.find_elements(By.CSS_SELECTOR, '.item-navigation.ng-scope')) <= num:
                if scroll_check >= 6: return cnt
                driver.execute_script('window.scrollTo(0, document.body.scrollHeight);')
                scroll_check += 1
                time.sleep(3)

            items = driver.find_elements(By.CSS_SELECTOR, '.item-navigation.ng-scope')
            # 「コレ！」ボタンの判定
            target_btn = items[num].find_elements(By.TAG_NAME, 'a')[0]

            if target_btn.get_attribute('class') == 'icon-hand left':
                target_btn.click()
                
                # 商品名の読み込みを待機
                WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CSS_SELECTOR, '.item-name.ng-binding')))
                
                # すでにコレ！済みでないか確認
                if len(driver.find_elements(By.CLASS_NAME, 'ok')) > 0:
                    driver.find_element(By.CLASS_NAME, 'ok').click()
                else:
                    # 投稿内容の構成
                    memo = config.get("memo", "")
                    title = driver.find_element(By.CSS_SELECTOR, '.item-name.ng-binding').text + "\n" + memo
                    hashtags = "\n\n#39ショップ #おすすめ #買ってよかった #おしゃれ #人気 #ランキング #ずっと欲しかった #あったら便利 #ポイント消化 #買い回り #買いまわり #お買い物マラソン #楽天スーパーSALE #お買い物メモ"
                    
                    driver.find_element(By.ID, 'collect-content').send_keys(title + hashtags)
                    time.sleep(1)
                    
                    # 完了ボタンクリック
                    driver.find_element(By.CSS_SELECTOR, '.button.button-red.collect-btn').click()
                    
                    # 完了後の×ボタンをクリックして閉じる
                    WebDriverWait(driver, 15).until(EC.presence_of_element_located((By.CLASS_NAME, 'icon-cross-normal')))
                    driver.find_element(By.CLASS_NAME, 'icon-cross-normal').click()
                    
                    cnt += 1
                    print(f"コレ！完了: {cnt}件目")
                    # 完了後の待機時間を削除（最短の猶予のみ）
                    time.sleep(1)
            else:
                time.sleep(0.5)
            num += 1
        except Exception as e:
            print(f"エラー（スキップ）: {e}")
            num += 1
            continue
    return cnt

if __name__ == '__main__':
    print(f"--- 実行開始: {dt.now()} ---")
    try:
        if not login():
            # ログインできないまま「成功」扱いにならないよう、失敗で終わらせる
            sys.exit(1)
        tag_used = search()
        if tag_used:
            # 実行回数（1件）
            result_cnt = kore(1)
            print(f"完了: 「{tag_used}」で {result_cnt} 商品を「コレ！」しました。")
    finally:
        driver.quit()
        print(f"--- 終了: {dt.now()} ---")
