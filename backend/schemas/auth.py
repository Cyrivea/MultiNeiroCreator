from pydantic import BaseModel, EmailStr, Field, field_validator


class AuthRequest(BaseModel):
    username: str
    password: str


class SendCodeRequest(BaseModel):
    """发送验证码只需要邮箱；EmailStr 替换旧的 `"@" in username` 检查。"""

    username: EmailStr
    password: str = ""


class RegisterRequest(BaseModel):
    """注册专用 Schema：校验在入口完成，进不了 service 的请求不需要防御代码。

    - username 用 EmailStr 做真正的邮箱格式校验（RFC 5322），替换旧的 `"@" in username`；
    - password 至少 8 位；上限按 UTF-8 字节数（bcrypt 只取前 72 字节，一个中文占 3 字节，
      超长应显式拒绝而不是让 bcrypt 静默截断）；
    - code 收进请求体，不再走 query string（query 会进服务器访问日志）。
    """

    username: EmailStr
    password: str = Field(min_length=8)
    code: str = Field(pattern=r"^\d{6}$")

    @field_validator("password")
    @classmethod
    def password_within_bcrypt_limit(cls, v: str) -> str:
        if len(v.encode("utf-8")) > 72:
            raise ValueError("密码过长（UTF-8 编码后不能超过 72 字节）")
        return v
