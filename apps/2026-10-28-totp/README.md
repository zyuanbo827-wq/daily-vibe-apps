# 2026-10-28 · totp —— TOTP/HOTP 动态口令

零依赖的两步验证（2FA）动态口令实现：手写 Base32、HOTP
（RFC 4226）、TOTP（RFC 6238），带时间窗口校验，附带 CLI。

## 功能

- **Base32 编解码**（RFC 4648）：无填充格式，兼容带 `=` 和
  空格/小写的输入
- **HOTP**：共享密钥 + 计数器，HMAC-SHA1 后动态截断取数字
- **TOTP**：把当前时间按步长（默认 30 秒）换算成计数器
- **校验窗口**：允许前后各 N 个时间步，容忍手机与服务器时钟
  漂移；比对使用恒定时间比较防时序攻击
- **密钥生成**：用 `secrets` 生成 160 位随机密钥，输出 Base32
  （可直接填入 Google Authenticator 等工具）

## 运行方式

需要 Python 3.8+，仅使用标准库。

```bash
# 生成密钥（Base32）
python totp.py genkey

# 取当前 6 位口令
python totp.py code GEZDGNBVGY3TQOJQ...

# 校验（默认前后各 1 个时间步）
python totp.py verify GEZDGNBVGY3TQOJQ... 818055

# 官方测试向量演示
python totp.py demo
```

作为库使用：

```python
from totp import generate_secret, base32_encode, totp, verify_totp
secret = generate_secret()
print(base32_encode(secret))
code = totp(secret)
verify_totp(code, secret)          # True
```

## 实现要点

1. **HOTP 动态截断**：HMAC-SHA1 输出 20 字节，取最后一个字节
  低 4 位作为偏移（0~15），从该位置读 4 字节，最高位清零（避免
  有符号问题），再对 10^digits 取模并前补零。
2. **TOTP 是 HOTP 的时间封装**：计数器 = `当前 Unix 秒 // 步长`，
  所以同一 30 秒窗口内所有设备算出同一口令，窗口一过自动更换。
3. **Base32 用位缓冲**：把字节按 5 位一组切分映射到 32 个字符；
  末尾不足 5 位时左补零。相比 Base64，Base32 只含大写字母和
  数字 2~7，人工录入、电话念读都不易出错。
4. **校验窗口**：不是只比对当前计数器，而是检查 `[counter-w,
  counter+w]`，解决双方时钟差几秒导致口令"刚换"的问题；窗口
  不宜过大，否则扩大了可被重放的范围。
5. **恒定时间比较**：`hmac.compare_digest` 逐字节比较，避免普通
  `==` 在口令长度/前缀上泄露计时信息。

## 测试

```bash
python -m unittest test_totp -v
```

共 15 个用例：
- Base32：RFC 4648 全部 7 组官方向量（`""/f/fo/foo/foob/fooba/
  foobar`）、40 组往返、填充与空格、非法字符
- HOTP：RFC 4226 附录 D 的计数器 0~9 全部 10 组口令
  （`755224, 287082, ...`）、位数与非法值
- TOTP：计数器推导、自定义步长、窗口校验、密钥生成
- CLI：demo 输出、genkey→code→verify 全链路、错误口令返回码

全部一次通过。
