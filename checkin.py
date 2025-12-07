#!/usr/bin/env python3
"""
AnyRouter.top 自动签到脚本（精简版）
"""

import asyncio
import json
import sys
from datetime import datetime

import httpx
from dotenv import load_dotenv
from playwright.async_api import async_playwright

from utils.config import AccountConfig, AppConfig, load_accounts_config

load_dotenv()


def parse_cookies(cookies_data):
	"""解析 cookies 数据"""
	if isinstance(cookies_data, dict):
		return cookies_data

	if isinstance(cookies_data, str):
		cookies_dict = {}
		for cookie in cookies_data.split(';'):
			if '=' in cookie:
				key, value = cookie.strip().split('=', 1)
				cookies_dict[key] = value
		return cookies_dict
	return {}


async def get_waf_cookies_with_playwright(account_name: str, login_url: str, required_cookies: list[str]):
	"""使用 Playwright 获取 WAF cookies"""
	print(f'[PROCESSING] {account_name}: Starting browser to get WAF cookies...')

	async with async_playwright() as p:
		import tempfile

		with tempfile.TemporaryDirectory() as temp_dir:
			context = await p.chromium.launch_persistent_context(
				user_data_dir=temp_dir,
				headless=False,
				user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/138.0.0.0 Safari/537.36',
				viewport={'width': 1920, 'height': 1080},
				args=[
					'--disable-blink-features=AutomationControlled',
					'--disable-dev-shm-usage',
					'--no-sandbox',
				],
			)

			page = await context.new_page()

			try:
				await page.goto(login_url, wait_until='networkidle')
				await page.wait_for_timeout(3000)

				cookies = await page.context.cookies()
				waf_cookies = {}
				for cookie in cookies:
					if cookie.get('name') in required_cookies:
						waf_cookies[cookie['name']] = cookie.get('value')

				missing = [c for c in required_cookies if c not in waf_cookies]
				if missing:
					print(f'[FAILED] {account_name}: Missing WAF cookies: {missing}')
					return None

				print(f'[SUCCESS] {account_name}: Got all WAF cookies')
				return waf_cookies

			except Exception as e:
				print(f'[FAILED] {account_name}: Error getting WAF cookies: {e}')
				return None
			finally:
				await context.close()


async def check_in_account(account: AccountConfig, index: int, app_config: AppConfig):
	"""为单个账号执行签到"""
	name = account.get_display_name(index)
	print(f'\n[PROCESSING] {name}')

	provider = app_config.get_provider(account.provider)
	if not provider:
		print(f'[FAILED] {name}: Provider "{account.provider}" not found')
		return False

	user_cookies = parse_cookies(account.cookies)
	if not user_cookies:
		print(f'[FAILED] {name}: Invalid cookies')
		return False

	# 获取 WAF cookies（如需要）
	if provider.needs_waf_cookies():
		login_url = f'{provider.domain}{provider.login_path}'
		waf_cookies = await get_waf_cookies_with_playwright(name, login_url, provider.waf_cookie_names)
		if not waf_cookies:
			return False
		all_cookies = {**waf_cookies, **user_cookies}
	else:
		all_cookies = user_cookies

	# 发起请求
	with httpx.Client(http2=True, timeout=30.0) as client:
		client.cookies.update(all_cookies)

		headers = {
			'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
			'Accept': 'application/json',
			'Referer': provider.domain,
			'Origin': provider.domain,
			provider.api_user_key: account.api_user,
		}

		# 获取用户信息
		try:
			resp = client.get(f'{provider.domain}{provider.user_info_path}', headers=headers)
			if resp.status_code == 200:
				data = resp.json()
				if data.get('success'):
					user = data.get('data', {})
					quota = round(user.get('quota', 0) / 500000, 2)
					used = round(user.get('used_quota', 0) / 500000, 2)
					print(f'[INFO] {name}: Balance ${quota}, Used ${used}')
		except Exception as e:
			print(f'[WARN] {name}: Failed to get user info: {e}')

		# 执行签到（如需要）
		if provider.needs_manual_check_in():
			try:
				headers['Content-Type'] = 'application/json'
				resp = client.post(f'{provider.domain}{provider.sign_in_path}', headers=headers)

				if resp.status_code == 200:
					result = resp.json()
					if result.get('success') or result.get('ret') == 1 or result.get('code') == 0:
						print(f'[SUCCESS] {name}: Check-in successful!')
						return True
					print(f'[FAILED] {name}: {result.get("msg", result.get("message", "Unknown error"))}')
					return False
				print(f'[FAILED] {name}: HTTP {resp.status_code}')
				return False
			except Exception as e:
				print(f'[FAILED] {name}: {e}')
				return False
		else:
			print(f'[SUCCESS] {name}: Check-in completed (auto)')
			return True


async def main():
	print('[SYSTEM] AnyRouter Check-in Script')
	print(f'[TIME] {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}')

	app_config = AppConfig.load_from_env()
	accounts = load_accounts_config()

	if not accounts:
		print('[FAILED] No account configuration found')
		sys.exit(1)

	print(f'[INFO] Found {len(accounts)} account(s)')

	success = 0
	for i, account in enumerate(accounts):
		if await check_in_account(account, i, app_config):
			success += 1

	print(f'\n[RESULT] {success}/{len(accounts)} succeeded')
	sys.exit(0 if success > 0 else 1)


if __name__ == '__main__':
	try:
		asyncio.run(main())
	except KeyboardInterrupt:
		print('\n[WARN] Interrupted')
		sys.exit(1)
