# 动态添加项目根目录到 sys.path，支持从任意位置运行
import sys
import os
_project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..'))
if _project_root not in sys.path:
    sys.path.insert(0, _project_root)


"""SSH 连接与底层命令执行（支持多主机与密钥认证）"""
import paramiko
import time
from typing import Tuple

from src.utils.settings import SettingsManager


def _get_auth_kwargs(host) -> dict:
    """
    根据主机配置生成 paramiko connect 的认证参数。
    优先使用私钥，其次密码。
    """
    kwargs = {
        "hostname": host.hostname,
        "port": host.port,
        "username": host.username,
        "timeout": 10,
    }
    if host.key_file and host.key_file.strip():
        try:
            key = paramiko.RSAKey.from_private_key_file(
                host.key_file, password=host.key_passphrase or None
            )
            kwargs["pkey"] = key
        except paramiko.SSHException:
            # 尝试其他密钥类型
            try:
                key = paramiko.Ed25519Key.from_private_key_file(
                    host.key_file, password=host.key_passphrase or None
                )
                kwargs["pkey"] = key
            except Exception:
                # 回退到密码
                kwargs["password"] = host.password
    else:
        kwargs["password"] = host.password
    return kwargs


def execute_ssh_command(command: str, timeout: int = 30, settings: SettingsManager = None) -> dict:
    """
    底层 SSH 执行函数（支持动态配置）。
    若传入 settings 则使用当前激活主机，否则回退到旧版 config.py 常量。
    返回标准 dict: {status, exit_code, output, error, execution_time, timeout_flag}
    """
    if settings is None:
        # 向后兼容：从旧版 config 读取
        from config.config import HOSTNAME, PORT, USERNAME, PASSWORD
        client_kwargs = {
            "hostname": HOSTNAME,
            "port": PORT,
            "username": USERNAME,
            "password": PASSWORD,
            "timeout": 10,
        }
    else:
        client_kwargs = _get_auth_kwargs(settings.active_host)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    start_time = time.time()

    try:
        client.connect(**client_kwargs)

        full_command = (
            f"export PATH=/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin:$PATH; "
            f"bash -l -c '{command}'"
        )

        stdin, stdout, stderr = client.exec_command(
            full_command,
            get_pty=True,
            timeout=timeout
        )

        exit_status = stdout.channel.recv_exit_status()
        output = stdout.read().decode('utf-8', errors='ignore').strip()
        error = stderr.read().decode('utf-8', errors='ignore').strip()
        execution_time = round(time.time() - start_time, 2)

        return {
            "status": "success" if exit_status == 0 else "failed",
            "exit_code": exit_status,
            "output": output,
            "error": error,
            "execution_time": execution_time,
            "timeout_flag": False
        }

    except paramiko.SSHException as e:
        execution_time = round(time.time() - start_time, 2)
        return {
            "status": "error",
            "message": f"SSH 连接异常：{str(e)}",
            "execution_time": execution_time,
            "timeout_flag": False
        }

    except TimeoutError:
        execution_time = round(time.time() - start_time, 2)
        return {
            "status": "error",
            "message": f"命令执行超时（超过 {timeout} 秒）。可能原因：\n"
                       f"1. 目标目录文件数量过多（如 /var/* 遍历大量文件）\n"
                       f"2. 网络延迟或 SSH 通道阻塞\n"
                       f"3. 命令本身需要较长时间完成\n"
                       f"建议：拆分命令范围，或增加超时时间",
            "execution_time": execution_time,
            "timeout_flag": True
        }

    except Exception as e:
        execution_time = round(time.time() - start_time, 2)
        return {
            "status": "error",
            "message": f"连接或执行异常：{str(e)}",
            "execution_time": execution_time,
            "timeout_flag": False
        }

    finally:
        client.close()


def is_permission_denied(result: dict) -> bool:
    """判断 SSH 执行结果是否为权限不足"""
    if result.get("status") != "failed":
        return False

    error = result.get("error", "")
    output = result.get("output", "")
    combined = (error + output).lower()

    permission_keywords = [
        "permission denied", "权限不足", "权限不够", "access denied",
        "operation not permitted", "not permitted",
        "cannot open directory", "cannot access", "拒绝访问"
    ]
    return any(kw in combined for kw in permission_keywords)


def test_connection(hostname: str, port: int, username: str,
                    password: str = "", key_file: str = "") -> Tuple[bool, str]:
    """
    测试 SSH 连接是否可用（不执行命令，仅握手）。
    返回: (是否成功, 提示信息)
    """
    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    kwargs = {
        "hostname": hostname,
        "port": port,
        "username": username,
        "timeout": 10,
    }
    if key_file and key_file.strip():
        try:
            key = paramiko.RSAKey.from_private_key_file(key_file)
            kwargs["pkey"] = key
        except Exception:
            try:
                key = paramiko.Ed25519Key.from_private_key_file(key_file)
                kwargs["pkey"] = key
            except Exception:
                kwargs["password"] = password
    else:
        kwargs["password"] = password

    try:
        client.connect(**kwargs)
        transport = client.get_transport()
        if transport and transport.is_active():
            version = transport.remote_version
            client.close()
            return True, f"SSH 连接成功 ({version})"
        client.close()
        return False, "SSH 传输层未激活"
    except paramiko.AuthenticationException as e:
        return False, f"认证失败: {e}"
    except paramiko.SSHException as e:
        return False, f"SSH 握手失败: {e}"
    except Exception as e:
        return False, f"连接异常: {e}"
    finally:
        client.close()
