from typing import Generic, TypeVar, Optional
from pydantic import BaseModel, Field

T = TypeVar('T')


class CommonResult(BaseModel, Generic[T]):
    """
    统一响应模型
    """
    code: int = Field(default=200, description="响应状态码")
    description: str = Field(default="success", description="响应消息")
    data: Optional[T] = Field(default=None, description="响应数据")

    def success(self, data: Optional[T] = None):
        self.code = 200
        self.description = "success"
        self.data = data
        return self

    def fail(self, code: int = 500, description: str = "fail"):
        self.code = code
        self.description = description
        return self 