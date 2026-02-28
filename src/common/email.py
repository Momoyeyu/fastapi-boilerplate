from loguru import logger


def send_verification_email(email: str, code: str, purpose: str) -> bool:
    purpose_text = "注册" if purpose == "register" else "重置密码"
    logger.info(f"[Email Mock] 发送{purpose_text}验证码到 {email}: {code}")
    return True
