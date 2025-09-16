"""
密码管理器
提供密码哈希、验证、强度检查等功能
"""

import re
import secrets
import string
from typing import Optional
import bcrypt
from dataclasses import dataclass


@dataclass
class PasswordStrength:
    """密码强度评估结果"""
    score: int  # 0-5分
    is_strong: bool
    feedback: list[str]
    missing_criteria: list[str]


class PasswordManager:
    """密码管理器"""

    def __init__(self, rounds: int = 12):
        """
        初始化密码管理器

        Args:
            rounds: bcrypt加密轮数，默认12轮
        """
        self.rounds = rounds

    def hash_password(self, password: str) -> str:
        """
        哈希密码

        Args:
            password: 明文密码

        Returns:
            哈希后的密码
        """
        if not password:
            raise ValueError("密码不能为空")

        # 生成盐值并哈希
        salt = bcrypt.gensalt(rounds=self.rounds)
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt)
        return hashed.decode('utf-8')

    def verify_password(self, password: str, hashed_password: str) -> bool:
        """
        验证密码

        Args:
            password: 明文密码
            hashed_password: 哈希后的密码

        Returns:
            密码是否匹配
        """
        if not password or not hashed_password:
            return False

        try:
            return bcrypt.checkpw(password.encode('utf-8'), hashed_password.encode('utf-8'))
        except (ValueError, TypeError):
            return False

    def generate_password(
        self,
        length: int = 16,
        use_uppercase: bool = True,
        use_lowercase: bool = True,
        use_digits: bool = True,
        use_symbols: bool = True,
        exclude_ambiguous: bool = True
    ) -> str:
        """
        生成随机密码

        Args:
            length: 密码长度
            use_uppercase: 是否包含大写字母
            use_lowercase: 是否包含小写字母
            use_digits: 是否包含数字
            use_symbols: 是否包含符号
            exclude_ambiguous: 是否排除易混淆字符

        Returns:
            生成的随机密码
        """
        if length < 4:
            raise ValueError("密码长度至少为4位")

        characters = ""

        # 构建字符集
        if use_lowercase:
            chars = string.ascii_lowercase
            if exclude_ambiguous:
                chars = chars.replace('l', '').replace('o', '')
            characters += chars

        if use_uppercase:
            chars = string.ascii_uppercase
            if exclude_ambiguous:
                chars = chars.replace('I', '').replace('O', '')
            characters += chars

        if use_digits:
            chars = string.digits
            if exclude_ambiguous:
                chars = chars.replace('0', '').replace('1')
            characters += chars

        if use_symbols:
            chars = "!@#$%^&*()-_=+[]{}|;:,.<>?"
            if exclude_ambiguous:
                chars = chars.replace('|', '').replace('l', '')
            characters += chars

        if not characters:
            raise ValueError("至少需要选择一种字符类型")

        # 确保每种选中的字符类型至少出现一次
        password = []

        if use_lowercase:
            chars = string.ascii_lowercase
            if exclude_ambiguous:
                chars = chars.replace('l', '').replace('o', '')
            password.append(secrets.choice(chars))

        if use_uppercase:
            chars = string.ascii_uppercase
            if exclude_ambiguous:
                chars = chars.replace('I', '').replace('O', '')
            password.append(secrets.choice(chars))

        if use_digits:
            chars = string.digits
            if exclude_ambiguous:
                chars = chars.replace('0', '').replace('1')
            password.append(secrets.choice(chars))

        if use_symbols:
            chars = "!@#$%^&*()-_=+[]{}|;:,.<>?"
            if exclude_ambiguous:
                chars = chars.replace('|', '').replace('l', '')
            password.append(secrets.choice(chars))

        # 填充剩余长度
        for _ in range(length - len(password)):
            password.append(secrets.choice(characters))

        # 随机打乱
        secrets.SystemRandom().shuffle(password)

        return ''.join(password)

    def check_password_strength(self, password: str) -> PasswordStrength:
        """
        检查密码强度

        Args:
            password: 要检查的密码

        Returns:
            密码强度评估结果
        """
        if not password:
            return PasswordStrength(
                score=0,
                is_strong=False,
                feedback=["密码不能为空"],
                missing_criteria=["所有条件"]
            )

        score = 0
        feedback = []
        missing_criteria = []

        # 长度检查
        length = len(password)
        if length >= 12:
            score += 2
            feedback.append("长度符合要求")
        elif length >= 8:
            score += 1
            feedback.append("长度一般")
        else:
            missing_criteria.append("至少8个字符")

        # 字符类型检查
        has_lower = bool(re.search(r'[a-z]', password))
        has_upper = bool(re.search(r'[A-Z]', password))
        has_digit = bool(re.search(r'[0-9]', password))
        has_symbol = bool(re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password))

        char_types = sum([has_lower, has_upper, has_digit, has_symbol])

        if char_types >= 3:
            score += 1
            feedback.append("包含多种字符类型")
        elif char_types >= 2:
            feedback.append("字符类型较少")
        else:
            missing_criteria.append("包含大小写字母、数字和符号")

        # 具体字符类型检查
        if not has_lower:
            missing_criteria.append("小写字母")
        if not has_upper:
            missing_criteria.append("大写字母")
        if not has_digit:
            missing_criteria.append("数字")
        if not has_symbol:
            missing_criteria.append("特殊符号")

        # 复杂度检查
        if not re.search(r'(.)\1{2,}', password):  # 没有连续3个相同字符
            score += 1
            feedback.append("没有重复字符")
        else:
            missing_criteria.append("避免连续重复字符")

        # 常见弱密码检查
        weak_patterns = [
            r'123456',
            r'password',
            r'qwerty',
            r'abc123',
            r'111111',
            r'admin'
        ]

        is_weak_pattern = any(re.search(pattern, password.lower()) for pattern in weak_patterns)
        if not is_weak_pattern:
            feedback.append("没有使用常见弱密码模式")
        else:
            score -= 1
            missing_criteria.append("避免使用常见弱密码")

        # 确保分数在0-5范围内
        score = max(0, min(5, score))

        # 判断是否为强密码
        is_strong = score >= 4 and length >= 12 and char_types >= 3

        return PasswordStrength(
            score=score,
            is_strong=is_strong,
            feedback=feedback,
            missing_criteria=missing_criteria
        )

    def generate_reset_token(self, length: int = 32) -> str:
        """
        生成密码重置令牌

        Args:
            length: 令牌长度

        Returns:
            随机令牌
        """
        return secrets.token_urlsafe(length)

    def is_password_compromised(self, password: str) -> bool:
        """
        检查密码是否在常见泄露密码列表中
        这里是简化实现，实际应该对接Have I Been Pwned等服务

        Args:
            password: 要检查的密码

        Returns:
            是否为已泄露密码
        """
        # 简化实现：检查一些常见弱密码
        common_passwords = {
            'password', '123456', 'password123', 'admin', 'qwerty',
            'letmein', 'welcome', 'monkey', '1234567890', 'abc123',
            'Password1', 'password1', 'root', 'toor', 'pass'
        }

        return password.lower() in common_passwords

    def validate_password_policy(self, password: str, username: str = None) -> tuple[bool, list[str]]:
        """
        验证密码是否符合安全策略

        Args:
            password: 要验证的密码
            username: 用户名（用于检查密码中是否包含用户名）

        Returns:
            (是否通过验证, 错误消息列表)
        """
        errors = []

        # 基本长度要求
        if len(password) < 8:
            errors.append("密码长度至少为8位")

        # 字符类型要求
        if not re.search(r'[a-z]', password):
            errors.append("密码必须包含小写字母")

        if not re.search(r'[A-Z]', password):
            errors.append("密码必须包含大写字母")

        if not re.search(r'[0-9]', password):
            errors.append("密码必须包含数字")

        if not re.search(r'[!@#$%^&*()_+\-=\[\]{}|;:,.<>?]', password):
            errors.append("密码必须包含特殊字符")

        # 检查是否包含用户名
        if username and username.lower() in password.lower():
            errors.append("密码不能包含用户名")

        # 检查是否为常见弱密码
        if self.is_password_compromised(password):
            errors.append("密码过于简单，请使用更复杂的密码")

        # 检查重复字符
        if re.search(r'(.)\1{2,}', password):
            errors.append("密码不能包含连续3个或以上相同字符")

        return len(errors) == 0, errors