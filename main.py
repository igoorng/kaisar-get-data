import json
import asyncio
import aiohttp
import pandas as pd
from threading import Lock

print_lock = Lock()
data_lock = Lock()

async def login(session, email, password):
    url = "https://zero-api.kaisar.io/auth/login"
    
    headers = {
        'accept': '*/*',
        'accept-language': 'zh-CN,zh;q=0.9',
        'content-type': 'application/json',
        'origin': 'https://zero.kaisar.io',
        'referer': 'https://zero.kaisar.io/'
    }
    
    data = {
        "email": email,
        "password": password
    }
    
    async with session.post(url, headers=headers, json=data) as response:
        return await response.json()

async def get_user_summary(session, token):
    url = "https://zero-api.kaisar.io/user/summary"
    
    headers = {
        'accept': '*/*',
        'accept-language': 'zh-CN,zh;q=0.9',
        'authorization': f'Bearer {token}',
        'content-type': 'application/json',
        'origin': 'https://zero.kaisar.io',
        'referer': 'https://zero.kaisar.io/'
    }
    
    async with session.get(url, headers=headers) as response:
        return await response.json()

async def process_email(session, email, all_data):
    try:
        with print_lock:
            print(f"处理邮箱: {email}")
        
        # 登录获取token
        login_response = await login(session, email, password)
        
        if "error" in login_response:
            with print_lock:
                print(f"账号未注册或登录失败: {email}")
                # 将失败的账号写入文件
                with open('account_error.txt', 'a', encoding='utf-8') as f:
                    f.write(f"{email}----{password}\n")
            return
            
        if "data" not in login_response:
            with print_lock:
                print(f"登录响应格式错误: {email}")
            return
            
        with print_lock:
            print(f"邮箱 {email} 登录成功")
        
        # 获取token和用户ID
        token = login_response["data"]["accessToken"]
        user_id = login_response["data"]["id"]
        
        # 获取用户统计信息
        summary = await get_user_summary(session, token)
        
        if "data" not in summary:
            with print_lock:
                print(f"获取统计信息失败: {email}")
            return
            
        # 收集数据
        data = {
            "ID": user_id,
            "邮箱": email,
            "密码": password, 
            "Total": summary["data"]["total"],
            "Today": summary["data"]["today"]
        }
        
        with data_lock:
            all_data.append(data)
            
        with print_lock:
            print(f"邮箱 {email} - Total: {data['Total']}, Today: {data['Today']}")
            
    except Exception as e:
        with print_lock:
            print(f"处理邮箱 {email} 时发生错误: {str(e)}")

async def main():
    try:
        with open('email.txt', 'r') as f:
            # 修改读取方式，解析email和password
            lines = [line.strip() for line in f if line.strip()]
            # 解析每行的email和password
            account_info = []
            for line in lines:
                if '----' in line:
                    email, password = line.split('----')
                    account_info.append((email.strip(), password.strip()))
    except FileNotFoundError:
        print("未找到email.txt文件")
        return

    all_data = []
    
    # 设置并发限制
    semaphore = asyncio.Semaphore(10)  # 限制并发数为10
    
    async with aiohttp.ClientSession() as session:
        async def bounded_process(account):
            email, password = account
            async with semaphore:
                await process_email(session, email, password, all_data)
        
        # 创建所有任务，使用account_info
        tasks = [bounded_process(account) for account in account_info]
        # 等待所有任务完成
        await asyncio.gather(*tasks)
        
    # 保存到Excel
    if all_data:
        df = pd.DataFrame(all_data)
        excel_file = 'kaisar_data.xlsx'
        df.to_excel(excel_file, index=False)
        print(f"数据已保存到 {excel_file}")
    else:
        print("没有数据需要保存")

if __name__ == "__main__":
    # Windows需要设置事件循环策略
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(main())
