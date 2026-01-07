#!/usr/bin/env python3
"""
测试词汇邮件任务
"""

import sys
import os
from datetime import datetime

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from backend.tasks.vocabulary_tasks import get_random_vocabulary, format_vocabulary_email, send_email

def test_get_random_vocabulary():
    """测试获取随机词汇"""
    print("Testing get_random_vocabulary...")
    vocabulary_list = get_random_vocabulary(10)
    print(f"Got {len(vocabulary_list)} vocabulary items")
    
    for i, vocab in enumerate(vocabulary_list, 1):
        print(f"{i}. {vocab['word']} ({vocab['part_of_speech']})")
        print(f"   Definition: {vocab['definition']}")
        if vocab['examples']:
            print(f"   Example: {vocab['examples'][0]}")
        print()
    
    return vocabulary_list

def test_format_vocabulary_email(vocabulary_list):
    """测试格式化词汇邮件"""
    print("Testing format_vocabulary_email...")
    subject, content = format_vocabulary_email(vocabulary_list)
    print(f"Subject: {subject}")
    print(f"Content preview: {content[:500]}...")
    print()
    return subject, content

def test_send_email(subject, content):
    """测试发送邮件"""
    print("Testing send_email...")
    test_email = "1290781598@qq.com"
    success = send_email(test_email, subject, content)
    print(f"Email sent: {success}")
    print()
    return success

def main():
    """主测试函数"""
    print(f"Starting vocabulary task test at {datetime.now()}")
    print("=" * 60)
    
    try:
        # 测试获取随机词汇
        vocabulary_list = test_get_random_vocabulary()
        
        if not vocabulary_list:
            print("No vocabulary found, test aborted")
            return
        
        # 测试格式化邮件
        subject, content = test_format_vocabulary_email(vocabulary_list)
        
        # 测试发送邮件
        test_send_email(subject, content)
        
        print("=" * 60)
        print("All tests completed successfully!")
        print(f"Test finished at {datetime.now()}")
        
    except Exception as e:
        print(f"Error during test: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
