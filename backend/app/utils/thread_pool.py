"""
线程池工具类
"""
import logging
from typing import Any, Callable, List, Optional, Tuple, Union
from concurrent.futures import ThreadPoolExecutor, Future, as_completed


class ThreadPoolManager:
    
    def __init__(self, max_workers):
        self.max_workers = max_workers
        self._executor: Optional[ThreadPoolExecutor] = None
    
    def __enter__(self):
        self._executor = ThreadPoolExecutor(max_workers=self.max_workers)
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        if self._executor:
            self._executor.shutdown(wait=True)
            self._executor = None
    
    def submit_task(self, func: Callable, *args, **kwargs) -> Future:

        if self._executor is None:
            raise RuntimeError("ThreadPoolManager not properly initialized. Use 'with' statement.")
        
        return self._executor.submit(func, *args, **kwargs)
    
    def _submit_multiple_tasks(self, func: Callable, tasks_args: List[tuple]) -> List[Future]:
        if self._executor is None:
            raise RuntimeError("ThreadPoolManager not properly initialized. Use 'with' statement.")
        
        futures = []
        for args in tasks_args:
            if isinstance(args, tuple):
                future = self._executor.submit(func, *args)
            else:
                future = self._executor.submit(func, args)
            futures.append(future)
        
        return futures
    
    def _wait_for_all_tasks(self, futures: List[Future], timeout: float = None, show_log: bool = True) -> List[Any]:
        results = []
        total_tasks = len(futures)
        completed_tasks = 0

        try:
            for future in as_completed(futures, timeout=timeout):
                try:
                    result = future.result()
                    results.append(result)
                    completed_tasks += 1
                    
                    # 打印进度
                    progress_percentage = (completed_tasks / total_tasks) * 100
                    if show_log:
                        logging.info(f"任务进度: {completed_tasks}/{total_tasks} ({progress_percentage:.1f}%) 完成")
                    
                except Exception as e:
                    logging.error(f"Task execution failed: {e}")
                    results.append(None)
                    completed_tasks += 1
                    
                    # 即使任务失败也要更新进度
                    progress_percentage = (completed_tasks / total_tasks) * 100
                    if show_log:
                        logging.info(f"任务进度: {completed_tasks}/{total_tasks} ({progress_percentage:.1f}%) 完成 (包含失败任务)")
                    
        except TimeoutError:
            logging.error(f"Tasks did not complete within {timeout} seconds")
            logging.info(f"超时时已完成: {completed_tasks}/{total_tasks} 个任务")
            for future in futures:
                if not future.done():
                    future.cancel()
        
        # 打印最终完成状态
        logging.info(f"所有任务执行完毕，共完成 {completed_tasks}/{total_tasks} 个任务")
        return results
    
    def execute_tasks_and_wait(self, func: Callable, tasks_args: List[tuple], 
                              timeout: float = None, show_log: bool = True) -> List[Any]:
        futures = self._submit_multiple_tasks(func, tasks_args)
        return self._wait_for_all_tasks(futures, timeout, show_log=show_log)
    
    def execute_multiple_functions(self, function_configs: List[Union[Callable, Tuple[Callable, tuple], Tuple[Callable, tuple, dict]]], 
                                 timeout: float = None, show_log: bool = True) -> List[Any]:
        """
        执行多个不同的函数并等待所有结果
        
        Args:
            function_configs: 函数配置列表，支持以下格式：
                - func: 无参数的函数
                - (func, args): 函数和位置参数元组
                - (func, args, kwargs): 函数、位置参数和关键字参数
            timeout: 超时时间（秒）
            
        Returns:
            结果列表，按提交顺序返回
        """
        if self._executor is None:
            raise RuntimeError("ThreadPoolManager not properly initialized. Use 'with' statement.")
        
        futures = []
        for config in function_configs:
            if callable(config):
                # 无参数的函数
                future = self._executor.submit(config)
            elif isinstance(config, tuple) and len(config) == 2:
                # (func, args)
                func, args = config
                if isinstance(args, tuple):
                    future = self._executor.submit(func, *args)
                else:
                    future = self._executor.submit(func, args)
            elif isinstance(config, tuple) and len(config) == 3:
                # (func, args, kwargs)
                func, args, kwargs = config
                if isinstance(args, tuple):
                    future = self._executor.submit(func, *args, **kwargs)
                else:
                    future = self._executor.submit(func, args, **kwargs)
            else:
                logging.error(f"Invalid function config: {config}")
                futures.append(None)
                continue
            futures.append(future)
        
        # 过滤掉None的futures
        valid_futures = [f for f in futures if f is not None]
        
        return self._wait_for_all_tasks(valid_futures, timeout, show_log=show_log)