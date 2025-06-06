"""
HTTP请求工具类
"""
import time
import functools
from typing import Any, Dict, Optional, Callable
import httpx
from loguru import logger

from backend.app.core.config import settings


def retryable(max_retries: int = 3, delay: float = 1.0, backoff: float = 2.0):
    """
    重试装饰器
    
    Args:
        max_retries: 最大重试次数
        delay: 初始延迟时间（秒）
        backoff: 退避倍数
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            current_delay = delay
            last_exception = None
            
            for attempt in range(max_retries + 1):  # +1 因为包含初始尝试
                try:
                    return func(*args, **kwargs)
                except Exception as e:
                    last_exception = e
                    if attempt < max_retries:
                        # logger.warning(
                        #     f"函数 {func.__name__} 第 {attempt + 1} 次尝试失败: {str(e)}，"
                        #     f"{current_delay:.1f}秒后重试"
                        # )
                        time.sleep(current_delay)
                        current_delay *= backoff
                    else:
                        logger.error(
                            f"函数 {func.__name__} 在 {max_retries + 1} 次尝试后仍然失败"
                        )
                        break
            
            raise last_exception
        return wrapper
    return decorator


class DebotHTTPUtils:
    """HTTP请求工具类"""

    
    @staticmethod
    @retryable(max_retries=5, delay=1.0, backoff=2.0)
    def get(
        endpoint: str,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 30.0
    ) -> Optional[Any]:
        """
        发送同步GET请求获取三方接口数据
        
        Args:
            endpoint: API端点，例如 "/api/v1/tokens"
            params: 查询参数
            headers: 请求头
            timeout: 超时时间（秒）
            
        Returns:
            响应的JSON数据
            
        Raises:
            httpx.HTTPError: HTTP请求异常
            ValueError: 响应不是有效的JSON格式
        """
        url = f"{settings.debot_api_url.rstrip('/')}/{endpoint.lstrip('/')}"

        with httpx.Client(timeout=timeout) as client:
            response = client.get(
                url=url,
                params=params,
                headers=headers
            )
            response.raise_for_status()
            try:
                data = response.json()
                # logger.info(f"成功获取数据，状态码: {response.status_code}")
                return data
            except ValueError as e:
                logger.error(f"响应不是有效的JSON格式: {response.text}")
                raise

    @staticmethod
    @retryable(max_retries=3, delay=1.0, backoff=2.0)
    def post(
        endpoint: str,
        json_data: Optional[Dict[str, Any]] = None,
        data: Optional[Dict[str, Any]] = None,
        params: Optional[Dict[str, Any]] = None,
        headers: Optional[Dict[str, str]] = None,
        timeout: float = 30.0
    ) -> Optional[Any]:
        """
        发送同步POST请求到三方接口
        
        Args:
            endpoint: API端点，例如 "/api/v1/tokens"
            json_data: JSON格式的请求体数据
            data: 表单格式的请求体数据
            params: 查询参数
            headers: 请求头
            timeout: 超时时间（秒）
            
        Returns:
            响应的JSON数据
            
        Raises:
            httpx.HTTPError: HTTP请求异常
            ValueError: 响应不是有效的JSON格式
        """
        url = f"{settings.debot_api_url.rstrip('/')}/{endpoint.lstrip('/')}"
        # logger.info(f"发送POST请求到: {url}")
        
        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                url=url,
                json=json_data,
                data=data,
                params=params,
                headers=headers
            )
            response.raise_for_status()
            try:
                data = response.json()
                # logger.info(f"成功获取数据，状态码: {response.status_code}")
                return data
            except ValueError as e:
                logger.error(f"响应不是有效的JSON格式: {response.text}")
                raise


class ThirdPartyHTTPUtils:

    @staticmethod
    @retryable(max_retries=3, delay=1.0, backoff=2.0)
    def get(
            url: str,
            params: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None,
            timeout: float = 30.0
    ) -> Optional[Any]:
        """
        发送同步GET请求获取三方接口数据

        Args:
            endpoint: API端点，例如 "/api/v1/tokens"
            params: 查询参数
            headers: 请求头
            timeout: 超时时间（秒）

        Returns:
            响应的JSON数据

        Raises:
            httpx.HTTPError: HTTP请求异常
            ValueError: 响应不是有效的JSON格式
        """

        with httpx.Client(timeout=timeout) as client:
            response = client.get(
                url=url,
                params=params,
                headers=headers
            )
            response.raise_for_status()
            try:
                data = response.json()
                # logger.info(f"成功获取数据，状态码: {response.status_code}")
                return data
            except ValueError as e:
                logger.error(f"响应不是有效的JSON格式: {response.text}")
                raise

    @staticmethod
    @retryable(max_retries=3, delay=1.0, backoff=2.0)
    def post(
            url: str,
            json_data: Optional[Dict[str, Any]] = None,
            data: Optional[Dict[str, Any]] = None,
            params: Optional[Dict[str, Any]] = None,
            headers: Optional[Dict[str, str]] = None,
            timeout: float = 30.0
    ) -> Optional[Any]:
        """
        发送同步POST请求到三方接口

        Args:
            endpoint: API端点，例如 "/api/v1/tokens"
            json_data: JSON格式的请求体数据
            data: 表单格式的请求体数据
            params: 查询参数
            headers: 请求头
            timeout: 超时时间（秒）

        Returns:
            响应的JSON数据

        Raises:
            httpx.HTTPError: HTTP请求异常
            ValueError: 响应不是有效的JSON格式
        """

        with httpx.Client(timeout=timeout) as client:
            response = client.post(
                url=url,
                json=json_data,
                data=data,
                params=params,
                headers=headers
            )
            response.raise_for_status()
            try:
                data = response.json()
                # logger.info(f"成功获取数据，状态码: {response.status_code}")
                return data
            except ValueError as e:
                logger.error(f"响应不是有效的JSON格式: {response.text}")
                raise