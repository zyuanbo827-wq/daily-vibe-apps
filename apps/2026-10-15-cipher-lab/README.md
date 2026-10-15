# 2026-10-15 · cipher-lab —— 古典密码实验台

零依赖的古典密码实验台：Caesar 凯撒移位（含 ROT13）、Vigenere
维吉尼亚密码，以及基于英文字母频率卡方评分的 Caesar 自动破解。
只处理 A-Z / a-z，大小写保留，非字母字符原样保留。

## 功能

- **Caesar**：每个字母在字母表上移动固定位数，支持负移位；
  26 为周期，取模自动回绕
- **ROT13**：Caesar 移位 13，是对合操作（加密两次还原）
- **Vigenere**：按密钥字母循环控制每位位移，多表替代；
  密钥自动过滤非字母字符；支持解密
- **频率分析破解**：
  - 统计密文 26 个字母频率，与英文标准频率做卡方距离
  - 枚举 26 个 Caesar 移位，卡方最小的即判为明文
  - 同时给出全量候选排序

## 运行方式

需要 Python 3.8+，仅使用标准库。

```bash
# 内置演示
python cipher.py demo

# Caesar（-d 解密，-s 移位数）
python cipher.py caesar "hello" -s 3
python cipher.py caesar "khoor" -s 3 -d

# ROT13
python cipher.py rot13 "hello"

# Vigenere（-k 密钥，-d 解密）
python cipher.py vigenere "ATTACKATDAWN" -k LEMON
python cipher.py vigenere "LXFOPVEFRNHR" -k LEMON -d

# 频率分析破解 Caesar 密文文件
python cipher.py crack sample_encrypted.txt
```

作为库使用：

```python
from cipher import caesar, vigenere, crack_caesar
caesar("xyz", 3)                       # "abc"
vigenere("ATTACKATDAWN", "LEMON")      # "LXFOPVEFRNHR"
shift, plain, score = crack_caesar(ciphertext)
```

## 实现要点

1. **取模回绕**：`(ord(ch) - base + shift) % 26 + base` 统一处理
  大写、小写、负移位和越过 Z/a 的回绕，非字母字符直接透传。
2. **Vigenere 是 26 个 Caesar 的循环复用**：密钥第 ki 个字母决定
  该位位移，密钥不足时循环；非字母字符不推进密钥指针，保证加
  解密严格对齐（经典向量 ATTACKATDAWN/LEMON → LXFOPVEFRNHR）。
3. **卡方破解的原理**：移位会把字母分布整体搬到错误的槽位，
  与英文标准频率的卡方距离骤增；枚举 26 个移位后，真实明文那
  一档分布归位、分数最小。短文本和罕见词会降低判据可靠性。
4. **ROT13 自逆**：26 是偶数且 13+13=26，故对同一文本做两次
  ROT13 即还原，这也是它常被用来“轻量遮蔽”而非加密的原因。
5. **安全提示**：Caesar 与 Vigenere 都只是教学用古典密码，
  密钥空间小、统计特征明显，绝不能用于真实敏感数据；现代加密
  应使用 AES 等标准算法与可靠的随机数。

## 测试

```bash
python -m unittest test_cipher -v
```

共 19 个用例：Caesar 已知向量、xyz 回绕、大小写与标点保留、
往返一致、ROT13 对合；Vigenere 经典向量、往返、非字母保留、
密钥清洗、空密钥报错；英文卡方低于移位文本、无字母文本返回
无穷、破解恢复移位 19 且还原全部明文、26 档候选完整；以及
demo、caesar/vigenere CLI、crack 文件（best shift 19）、缺文件
退出码 2 的子进程冒烟。

开发中发现并修复 1 处样例问题：用 Windows PowerShell
`Set-Content -Encoding UTF8` 生成密文样例时被写入 BOM 且丢失
行尾换行，导致破解明文与样例不一致；改用 Python 以 UTF-8 无
BOM、原始换行写出后 19 个用例全部通过。
