import os
import httpx
import qrcode
import asyncio
from jsonpath import jsonpath
from loguru import logger
from dotenv import load_dotenv

load_dotenv()


def validation_response(response, asserts=None):
    """验证响应是否有效"""
    if (
        response.status_code != 200
        and response.status_code != 302
        and response.status_code != 301
    ):
        return False
    if asserts:
        for key, value in asserts.items():
            if jsonpath(response.json(), f"$.{key}")[0] != value:
                return False
    return True


# TODO:包装成class
async def get_qr(client: httpx.AsyncClient):
    """获取二维码"""
    url = "{}/sdk/webs/platform/get-qr-code".format(BASE_HOST)
    resp = await client.get(url)
    if validation_response(resp, {"result": "ok"}):
        print("获取二维码成功")
        # 拼接二维码链接 生成二维码,并在控制台显示
        qr_url = "{}://qr_login?login_id={}".format(QR_HOST, resp.json()["qr_code"])
        qr = qrcode.QRCode()
        qr.add_data(qr_url)
        qr.print_ascii(invert=True)
        return resp.json()["qr_code"]


async def get_token(client: httpx.AsyncClient, qr_code):
    """验证二维码是否扫描"""
    url = "{}/sdk/webs/platform/login-qrcode?qr_code={}".format(BASE_HOST, qr_code)
    for _ in range(30):
        resp = await client.get(url)
        if validation_response(resp, {"result": "ok"}):
            logger.success("登录成功")
            return resp.json()
        else:
            logger.info(resp.json().get("error_msg"))
        await asyncio.sleep(5)
    else:
        logger.error("登录超时")


async def set_auth_cookie(client: httpx.AsyncClient, token):
    url = "{}{}".format(BASE_HOST, token)
    resp = await client.get(url)
    if validation_response(resp):
        return resp.text


async def is_admin(client: httpx.AsyncClient):
    """判断是否为管理员"""
    url = "{}/sdk/company/is_admin".format(BASE_HOST)
    resp = await client.get(url)
    if validation_response(resp, {"result": "ok"}):
        return resp.json()


async def woeker():
    # TODO: 读取token
    is_login = False
    while True:
        try:
            async with httpx.AsyncClient(follow_redirects=True) as client:
                if not is_login:
                    qr_code = await get_qr(client)
                    if qr_code:
                        login_data = await get_token(client, qr_code)
                        if login_data:
                            # 清理控制台
                            print("\033c")
                            is_login = True
                            await set_auth_cookie(
                                client, login_data["redir"]
                            )  # 设置cookie
                            # logger.info(login_data)
                            # TODO: 保存token到本地
                if is_login:
                    account_info = await is_admin(client)
                    print(account_info)
                    # id $.companyUser.data.ucard.id
                    # name $.companyUser.data.ucard.name
                    # career $.companyUser.data.ucard.career
                    # is_company_vip $.companyUser.data.is_company_vip

                    # /groundhog/msg/v5/get_dlg
        except Exception as e:
            # logger.error(e)
            logger.exception(e)
        finally:
            await asyncio.sleep(int(os.environ.get("interval")))


async def main():
    # 本来想加多账号,想想还是算了,只有一个号 tasks = []
    await asyncio.gather(asyncio.create_task(woeker()))


if __name__ == "__main__":
    # 如果文件为空,那就不会进行任何回复,只会打印消息列表
    # 如果有感兴趣的内容,就会自动回复或点击感兴趣
    BASE_HOST = bytes.fromhex("68747470733a2f2f6d61696d61692e636e").decode()
    QR_HOST = bytes.fromhex("74616f756d61696d6169").decode()
    subscribe_list = os.environ.get("subscribe").split("|")
    asyncio.run(main())
