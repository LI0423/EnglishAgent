#!/usr/bin/env python3
"""
启动Celery worker和beat服务的脚本
"""
import subprocess
import sys
import os


def start_celery_worker():
    """启动Celery worker"""
    print("Starting Celery worker...")
    
    # 切换到项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    
    # 启动Celery worker
    worker_cmd = [
        sys.executable,
        '-m', 'celery',
        '-A', 'backend.tasks',
        'worker',
        '--loglevel=info',
        '--concurrency=4'
    ]
    
    try:
        subprocess.Popen(worker_cmd)
        print("Celery worker started successfully")
    except Exception as e:
        print(f"Error starting Celery worker: {e}")


def start_celery_beat():
    """启动Celery beat"""
    print("Starting Celery beat...")
    
    # 切换到项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    
    # 启动Celery beat
    beat_cmd = [
        sys.executable,
        '-m', 'celery',
        '-A', 'backend.tasks',
        'beat',
        '--loglevel=info'
    ]
    
    try:
        subprocess.Popen(beat_cmd)
        print("Celery beat started successfully")
    except Exception as e:
        print(f"Error starting Celery beat: {e}")


def start_flower():
    """启动Flower监控"""
    print("Starting Flower monitoring...")
    
    # 切换到项目根目录
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    os.chdir(project_root)
    
    # 启动Flower
    flower_cmd = [
        sys.executable,
        '-m', 'flower',
        '-A', 'backend.tasks',
        '--port=5555'
    ]
    
    try:
        subprocess.Popen(flower_cmd)
        print("Flower started successfully at http://localhost:5555")
    except Exception as e:
        print(f"Error starting Flower: {e}")


def main():
    """主函数"""
    print("Starting Celery services...")
    
    # 启动Celery worker
    start_celery_worker()
    
    # 等待2秒，确保worker启动
    import time
    time.sleep(2)
    
    # 启动Celery beat
    start_celery_beat()
    
    # 启动Flower监控
    start_flower()
    
    print("All Celery services started successfully!")
    print("To stop services, use Ctrl+C or kill the processes")


if __name__ == '__main__':
    main()
